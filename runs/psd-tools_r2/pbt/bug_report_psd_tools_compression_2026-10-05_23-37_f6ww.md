# Bug Report: psd_tools.compression Malformed Channel Data Raises AssertionError/IndexError or Is Silently Accepted Under -O

**Target**: `psd_tools.compression.decompress`, `psd_tools.compression._rle.decode`
**Severity**: Medium
**Bug Type**: Contract
**Date**: 2026-10-05

## Summary

`decompress` checks the output length only with an `assert`. Malformed or truncated channel data therefore raises `AssertionError` (or `IndexError`) instead of the `ValueError` that the RLE path uses everywhere else. Under `python -O` the check disappears and `decompress` silently returns a buffer of the wrong size. Separately, the Cython RLE decoder `_rle.decode` raises `IndexError` on a trailing repeat header, while the pure-Python reference `rle.decode` raises `ValueError`. The reference also reports a misleading message: "Expected 11 bytes but decoded 11 bytes".

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from psd_tools.compression import rle as py_rle, _rle as c_rle

@settings(max_examples=3000)
@given(st.binary(max_size=40), st.integers(0, 60))
def test_rle_decode_impls_agree(data, size):
    def run(f):
        try:
            return ("ok", bytes(f(data, size)))
        except ValueError:
            return ("err", None)
    assert run(py_rle.decode) == run(c_rle.decode)
```

**Failing input**: `data=b"\x00\x00\xf7", size=11` (Cython: `IndexError`; Python: `ValueError`). The `decompress` fuzz test also failed with `payload=b"", w=1, h=1, d=8, comp=RLE` (`AssertionError: len=0, expected=1`) and with `payload=zlib.compress(b""), d=32, comp=ZIP_WITH_PREDICTION` (`IndexError: array index out of range`).

## Reproducing the Bug

```python
import zlib
from psd_tools.compression import decompress, rle, _rle
from psd_tools.constants import Compression

try: _rle.decode(b"\x00\x00\xf7", 11)
except Exception as e: print(type(e).__name__, e)   # IndexError
try: rle.decode(b"\x00\x00\xf7", 11)
except Exception as e: print(type(e).__name__, e)   # ValueError: Expected 11 bytes but decoded 11 bytes

print(len(decompress(b"", Compression.RLE, 10, 10, 8)))                       # AssertionError; under `python -O` prints 0
print(len(decompress(zlib.compress(b"abc"), Compression.ZIP, 10, 10, 8)))     # AssertionError; under `python -O` prints 3
decompress(zlib.compress(b""), Compression.ZIP_WITH_PREDICTION, 1, 1, 32)     # IndexError
```

## Why This Is A Bug

These functions parse untrusted file data. `decode_rle` explicitly catches and logs `ValueError` as its "invalid data" signal, and the pure-Python reference raises `ValueError`, but the default Cython implementation leaks `IndexError`. Using `assert` for input validation is incorrect: optimized mode strips it, so callers get channel buffers of the wrong length that break later in unexpected places (for example when building PIL/NumPy images). The pure-Python error message also prints `j` (which counts phantom bytes) instead of `len(result)`, so it hides the real mismatch.

## Fix

```diff
--- a/src/psd_tools/compression/__init__.py
+++ b/src/psd_tools/compression/__init__.py
-        else:
-            assert len(result) == length, "len=%d, expected=%d" % (len(result), length)
+        elif len(result) != length:
+            raise ValueError("len=%d, expected=%d" % (len(result), length))
@@ def decode_prediction(data: bytes, w: int, h: int, depth: int) -> bytes:
+    if len(data) != w * h * depth // 8:
+        raise ValueError("Invalid prediction data length %d" % len(data))
--- a/src/psd_tools/compression/_rle.pyx
+++ b/src/psd_tools/compression/_rle.pyx
         if bit > 128:
             bit = 256 - bit
-            if j+1+bit > size:
+            if i >= length or j+1+bit > size:
                 raise ValueError('Invalid RLE compression')
--- a/src/psd_tools/compression/rle.py
+++ b/src/psd_tools/compression/rle.py
         if bit > 128:
             bit = 256 - bit
-            if j + 1 + bit > size:
+            if i >= length or j + 1 + bit > size:
                 raise ValueError("Invalid RLE compression")
```

# Bug Report: psd_tools.compression RLE decoder raises IndexError on truncated repeat run

**Target**: `psd_tools.compression._rle.decode` / `psd_tools.compression.decode_rle` / `psd_tools.compression.decompress`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-06

## Summary

If PackBits data ends with a repeat header (a byte > 128) and no value byte after it, the Cython decoder raises `IndexError`. The pure-Python fallback raises `ValueError` for the same input. `decode_rle` only handles `ValueError`, so the `IndexError` skips its error logging and goes straight up through `decompress()` to anyone parsing the PSD. The pure-Python decoder doesn't check bounds here either: it adds the repeat count to `j` even though it copies no bytes, so its error message is wrong ("Expected 75 bytes but decoded 75 bytes").

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from psd_tools.compression import rle, _rle

@settings(max_examples=3000)
@given(st.binary(max_size=50), st.integers(0, 100))
def test_rle_decode_equiv(data, size):
    res = []
    for impl in (rle, _rle):
        try:
            res.append(("ok", bytes(impl.decode(data, size))))
        except ValueError:
            res.append(("err", None))
    assert res[0] == res[1]
    if res[0][0] == "ok" and size:
        assert len(res[0][1]) == size
```

**Failing input**: `data=b'\x00\x00\xb7', size=75`

## Reproducing the Bug

```python
from psd_tools.compression import rle, _rle, decompress
from psd_tools.constants import Compression

try:
    rle.decode(b'\x00\x00\xb7', 75)
except Exception as e:
    print(type(e).__name__, e)   # ValueError Expected 75 bytes but decoded 75 bytes

_rle.decode(b'\x00\x00\xb7', 75)  # IndexError: Out of bounds on buffer access (axis 0)

decompress(b'\x00\x03\x00\x00\xb7', Compression.RLE, 75, 1, 8, 1)  # IndexError
```

## Why This Is A Bug

The two RLE implementations are documented as drop-in replacements ("graceful fallback to pure Python"). Here they raise different exception types. Callers (`decode_rle`, and through it, PSD parsing) expect `ValueError` for invalid RLE data. Any truncated or malformed RLE channel in an untrusted PSD triggers this. In the repeat branch, neither decoder checks that a value byte follows the header. The literal branch does check this (`i+1+bit > length`).

## Fix

```diff
--- a/src/psd_tools/compression/_rle.pyx
+++ b/src/psd_tools/compression/_rle.pyx
@@
         if bit > 128:
             bit = 256 - bit
-            if j+1+bit > size:
+            if i >= length or j+1+bit > size:
                 raise ValueError('Invalid RLE compression')
--- a/src/psd_tools/compression/rle.py
+++ b/src/psd_tools/compression/rle.py
@@
         if bit > 128:
             bit = 256 - bit
-            if j + 1 + bit > size:
+            if i >= length or j + 1 + bit > size:
                 raise ValueError("Invalid RLE compression")
```

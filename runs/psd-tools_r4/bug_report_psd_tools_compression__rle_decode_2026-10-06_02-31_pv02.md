# Bug Report: psd_tools.compression Cython RLE decoder raises IndexError on truncated repeat run

**Target**: `psd_tools.compression._rle.decode` (used by `decode_rle` / `decompress`)
**Severity**: Low
**Bug Type**: Crash
**Date**: 2026-10-06

## Summary

If RLE input ends with a repeat header byte (>128) that has no data byte after it, the Cython decoder raises `IndexError`. The pure-Python reference decoder raises `ValueError` for the same input. `decode_rle` only handles `ValueError`, so its error logging is skipped. Callers that expect the documented `ValueError` for invalid RLE data get an unexpected exception type when they parse a malformed PSD.

## Property-Based Test

```python
@settings(max_examples=2000)
@given(st.binary(max_size=200), st.integers(0, 300))
def test_rle_impls_agree_decode(data, size):
    def run(f):
        try:
            return ("ok", bytes(f(data, size)))
        except ValueError:
            return ("err", None)
    p, c = run(py_rle.decode), run(cy_rle.decode)
    assert p == c
```

**Failing input**: `data=b'\x00\x00\xbc', size=70`

## Reproducing the Bug

```python
from psd_tools.compression import rle, _rle, decode_rle

bad = b"\x00\x00\xbc"
try:
    rle.decode(bad, 70)
except ValueError as e:
    print("python:", e)
_rle.decode(bad, 70)
```

The Python version raises `ValueError: Expected 70 bytes but decoded 70 bytes`, and the error message is also misleading. The Cython version raises `IndexError: Out of bounds on buffer access (axis 0)`. `decode_rle(b"\x00\x03" + bad, 70, 1, 8, 1)` raises the same `IndexError`.

## Why This Is A Bug

Both decoders signal invalid RLE data with `ValueError('Invalid RLE compression')`, and the module docs say the Cython version is a drop-in replacement for the Python one. Bounds checking stops memory corruption, but the exception type depends on which backend is installed, and the `except ValueError` handler in `decode_rle` is bypassed. In the Python version, `j` is advanced by the claimed run length even when no byte was produced, which causes the "Expected 70 but decoded 70" message.

## Fix

```diff
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

# Bug Report: psd_tools.compression Cython RLE decoder raises IndexError instead of ValueError on truncated input

**Target**: `psd_tools.compression._rle.decode` (used by `decode_rle` / `decompress`)
**Severity**: Low
**Bug Type**: Contract
**Date**: 2026-10-06

## Summary

When an RLE stream ends with a repeat header byte (>128) but has no value byte after it, the Cython decoder reads past the end of the buffer and raises `IndexError`. The pure-Python reference decoder raises `ValueError` for the same input. The package says the Cython version is a drop-in replacement for the Python fallback.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from psd_tools.compression import rle as py_rle, _rle as cy_rle

def _call(f, *a):
    try:
        return ("ok", bytes(f(*a)))
    except Exception as e:
        return ("err", type(e).__name__)

@settings(max_examples=2000)
@given(st.binary(max_size=40), st.integers(0, 60))
def test_rle_decode_equivalence(data, size):
    assert _call(py_rle.decode, data, size) == _call(cy_rle.decode, data, size)
```

**Failing input**: `data=b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xf7', size=15`

## Reproducing the Bug

```python
from psd_tools.compression import rle, _rle

try: rle.decode(b"\x00\x00\xff", 3)
except Exception as e: print(repr(e))   # ValueError("Expected 3 bytes but decoded 3 bytes")
_rle.decode(b"\x00\x00\xff", 3)          # IndexError: Out of bounds on buffer access (axis 0)
```

## Why This Is A Bug

Every other kind of malformed input makes both implementations raise `ValueError("Invalid RLE compression")`. `decode_rle` only catches `ValueError` to log its diagnostics, so with the Cython build (the default) these truncated streams skip that path. Any caller that catches `ValueError` to handle corrupt channel data will also miss them. The Python decoder also forgets to check `i < length` before reading the repeat byte. It only fails later, at the final length check, and the message is misleading ("Expected 3 bytes but decoded 3 bytes") because it reports the counter `j` instead of `len(result)`.

## Fix

```diff
         if bit > 128:
             bit = 256 - bit
-            if j+1+bit > size:
+            if i >= length or j+1+bit > size:
                 raise ValueError('Invalid RLE compression')
```
(The same `i >= length` check should be added to `rle.py`.)

# Bug Report: psd_tools.compression RLE Decoding Raises IndexError/AssertionError Instead of ValueError on Malformed Data

**Target**: `psd_tools.compression._rle.decode`, `psd_tools.compression.decompress` (RLE)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-05

## Summary

The RLE codecs are meant to raise `ValueError("Invalid RLE compression")` on malformed input, and `decode_rle` catches and logs only `ValueError`. Two kinds of malformed input break this:

1. **Cython decoder:** if a repeat header is the last byte of the input, `_rle.decode` raises `IndexError`. The pure-Python fallback `rle.decode` raises `ValueError` on the same input, so the two implementations disagree.
2. **Truncated row byte-counts table:** if the table is shorter than `height`, `read_be_array` silently returns fewer counts. `decode_rle` then returns too few bytes, and `decompress` fails with a bare `AssertionError`. Under `python -O` the assert is removed and a buffer of the wrong length is returned.

## Property-Based Test

```python
@settings(max_examples=3000)
@given(st.binary(), st.integers(0, 600))
def test_decode_equivalence(data, size):
    res = []
    for dec in (py_rle.decode, c_rle.decode):
        try:
            res.append(("ok", bytes(dec(data, size))))
        except ValueError:
            res.append(("err", None))
    assert res[0] == res[1]


@settings(max_examples=2000)
@given(st.binary(max_size=200), st.integers(1, 20), st.integers(1, 10),
       st.sampled_from([8, 16, 32]), st.sampled_from([1, 2]))
def test_decompress_rle_garbage(data, w, h, depth, version):
    try:
        out = decompress(data, Compression.RLE, w, h, depth, version)
    except ValueError:
        return
    assert len(out) == w * h * depth // 8
```

**Failing input**: `data=b'\x00\x00\xec', size=22` (equivalence); `data=b'', w=1, h=1, depth=8, version=1` (decompress)

## Reproducing the Bug

```python
from psd_tools.compression import _rle, rle, decompress
from psd_tools.constants import Compression

try:
    rle.decode(b"\x00\x00\xec", 22)
except ValueError as e:
    print("python:", e)

_rle.decode(b"\x00\x00\xec", 22)  # IndexError: Out of bounds on buffer access (axis 0)

decompress(b"", Compression.RLE, 1, 2, 8, 1)  # AssertionError: len=0, expected=2
```

## Why This Is A Bug

The Cython module is documented as a drop-in, faster replacement for `rle.py`, but it raises a different exception type on the same input. `decode_rle` explicitly handles `ValueError` to log RLE failures, and callers in `psd_tools.psd` catch `ValueError` for malformed data. Any PSD with truncated or corrupt RLE channel data therefore escapes as `IndexError` or `AssertionError`. A side issue: the Python decoder's error message is misleading ("Expected 22 bytes but decoded 22 bytes"), because it reports `j`, which counts bytes that were never written.

## Fix

```diff
--- a/src/psd_tools/compression/_rle.pyx
+++ b/src/psd_tools/compression/_rle.pyx
@@ def decode(const unsigned char[:] data, Py_ssize_t size) -> string:
         if bit > 128:
             bit = 256 - bit
-            if j+1+bit > size:
+            if i >= length or j+1+bit > size:
                 raise ValueError('Invalid RLE compression')
--- a/src/psd_tools/compression/rle.py
+++ b/src/psd_tools/compression/rle.py
@@ def decode(data: bytes, size: int) -> bytes:
         if bit > 128:
             bit = 256 - bit
-            if j + 1 + bit > size:
+            if i >= length or j + 1 + bit > size:
                 raise ValueError("Invalid RLE compression")
--- a/src/psd_tools/compression/__init__.py
+++ b/src/psd_tools/compression/__init__.py
@@ def decode_rle(data: bytes, width: int, height: int, depth: int, version: int) -> bytes:
             bytes_counts = read_be_array(("H", "I")[version - 1], height, fp)
+            if len(bytes_counts) != height:
+                raise ValueError("Truncated RLE byte counts")
@@ def decompress(
-            assert len(result) == length, "len=%d, expected=%d" % (len(result), length)
+            if len(result) != length:
+                raise ValueError("len=%d, expected=%d" % (len(result), length))
```

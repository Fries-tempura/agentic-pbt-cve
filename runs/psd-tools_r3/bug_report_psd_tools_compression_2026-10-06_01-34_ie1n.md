# Bug Report: psd_tools.compression RLE row size is wrong for 1-bit (bitmap) images whose width is not a multiple of 8

**Target**: `psd_tools.compression.encode_rle` / `decode_rle` (via `compress` / `decompress`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`encode_rle` and `decode_rle` compute the row size as `width * depth // 8`, which rounds **down**. In PSD bitmap mode (depth 1), each scanline is padded to a whole number of bytes, so the row size must be `ceil(width * depth / 8)`. When the width is not a multiple of 8:
- `compress(..., Compression.RLE, ...)` silently drops data: the encoder reads too few bytes per row.
- `decompress(..., Compression.RLE, ...)` rejects valid, spec-conformant RLE streams.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from psd_tools.compression import compress, decompress
from psd_tools.constants import Compression

@st.composite
def bitmap(draw):
    w = draw(st.integers(1, 40))
    h = draw(st.integers(1, 6))
    n = ((w + 7) // 8) * h  # PSD bitmap rows are padded to whole bytes
    return draw(st.binary(min_size=n, max_size=n)), w, h

@settings(max_examples=500)
@given(bitmap(), st.sampled_from([Compression.RLE, Compression.ZIP]), st.sampled_from([1, 2]))
def test_bitmap_roundtrip(img, comp, version):
    data, w, h = img
    c = compress(data, comp, w, h, 1, version)
    assert decompress(c, comp, w, h, 1, version) == data
```

**Failing input**: `img=(b'\x00\x00', 9, 1), comp=Compression.RLE, version=1` (also `img=(b'\x00', 1, 1)`, which raises `ValueError`)

## Reproducing the Bug

```python
from psd_tools.compression import compress, decompress
from psd_tools.constants import Compression

data = bytes([0xAA, 0xC0, 0x55, 0x40])  # 10x2 bitmap, 2 bytes per padded row
c = compress(data, Compression.RLE, 10, 2, 1, 1)
print(decompress(c, Compression.RLE, 10, 2, 1, 1))  # b'\xaa\xc0' -- half the data lost

spec = b"\x00\x03\x00\x03" + b"\x01\xaa\xc0" + b"\x01\x55\x40"  # conformant PackBits stream
decompress(spec, Compression.RLE, 10, 2, 1, 1)  # ValueError: Invalid RLE compression

compress(b"\x00", Compression.RLE, 1, 1, 1, 1)  # encodes 0 bytes per row
decompress(compress(b"\x00", Compression.RLE, 1, 1, 1, 1), Compression.RLE, 1, 1, 1, 1)  # ValueError
```

## Why This Is A Bug

The module docstring describes `compress`/`decompress` as a symmetric codec, and the round-trip already works for RAW/ZIP and for 8/16/32-bit data. Bitmap-mode PSDs with RLE (what Photoshop usually writes) use byte-padded scanlines. psd-tools therefore can't read such files when the width % 8 != 0, and when it writes them, the pixel data is silently truncated. For depth=1, `decompress` also skips the length assertion, so nothing reports the truncation.

## Fix

```diff
 def encode_rle(data: bytes, width: int, height: int, depth: int, version: int) -> bytes:
-    row_size = width * depth // 8
+    row_size = (width * depth + 7) // 8
     with io.BytesIO(data) as fp:
@@
 def decode_rle(data: bytes, width: int, height: int, depth: int, version: int) -> bytes:
     try:
-        row_size = max(width * depth // 8, 1)
+        row_size = max((width * depth + 7) // 8, 1)
         with io.BytesIO(data) as fp:
```

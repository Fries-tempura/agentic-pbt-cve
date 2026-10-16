# Bug Report: psd_tools.compression RLE drops trailing row bytes for 1-bit images

**Target**: `psd_tools.compression.encode_rle` / `decode_rle` (via `compress`/`decompress`)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

For `depth=1` (bitmap mode), `encode_rle` and `decode_rle` compute the row size as `width * depth // 8`, which rounds down. A bitmap row needs `ceil(width / 8)` bytes, so when the width isn't a multiple of 8 each row loses its last, padded byte. RLE round-trips then silently drop data, and decoding produces too few bytes for the consumers in `psd_tools.api`.

## Property-Based Test

```python
@settings(max_examples=300)
@given(st.integers(1, 64), st.integers(1, 20), st.sampled_from([1, 2]), st.data())
def test_compress_roundtrip_depth1(w, h, version, d):
    rowbytes = (w + 7) // 8
    data = d.draw(st.binary(min_size=rowbytes * h, max_size=rowbytes * h))
    c = compress(data, Compression.RLE, w, h, 1, version)
    assert decompress(c, Compression.RLE, w, h, 1, version) == data
```

**Failing input**: `w=9, h=1, version=1, data=b'\x00\x00'` (and `w=1, h=1` raises `ValueError: Expected 1 bytes but decoded 0 bytes`, because `encode_rle` reads 0 bytes per row)

## Reproducing the Bug

```python
from PIL import Image
from psd_tools.compression import compress, decompress
from psd_tools.constants import Compression

data = b"\xff\x80"
c = compress(data, Compression.RLE, 9, 1, 1, 1)
out = decompress(c, Compression.RLE, 9, 1, 1, 1)
assert out == data, out
Image.frombytes("1", (9, 1), out, "raw", "1;I")
```

`out` is `b'\xff'`, and `Image.frombytes` raises `ValueError: not enough image data`.

## Why This Is A Bug

`compress`/`decompress` are documented as inverse codecs for channel data, and `psd_tools.api.pil_io._create_image` decodes depth-1 data with `Image.frombytes("1", size, data, "raw", "1;I")`, which expects `ceil(width/8)` bytes per row. In PSD bitmap mode each scanline is padded to a byte boundary, so a 9-pixel-wide row is 2 bytes. With the floor division, bitmap layers or images whose width isn't a multiple of 8 can't be decoded, or are corrupted when they are re-encoded. For `width < 8`, `encode_rle` reads 0 bytes per row and writes empty rows.

## Fix

```diff
 def encode_rle(data: bytes, width: int, height: int, depth: int, version: int) -> bytes:
-    row_size = width * depth // 8
+    row_size = (width * depth + 7) // 8
@@
 def decode_rle(data: bytes, width: int, height: int, depth: int, version: int) -> bytes:
     try:
-        row_size = max(width * depth // 8, 1)
+        row_size = max((width * depth + 7) // 8, 1)
```

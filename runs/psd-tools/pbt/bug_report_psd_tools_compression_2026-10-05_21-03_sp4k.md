# Bug Report: psd_tools.compression.decompress Unbounded ZIP Decompression (Decompression Bomb)

**Target**: `psd_tools.compression.decompress`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

For `Compression.ZIP` and `Compression.ZIP_WITH_PREDICTION`, `decompress` calls `zlib.decompress(data)` with no output limit, even though it already knows the expected size (`width * height * depth // 8`). The size check only runs after the whole stream has been inflated. A channel of about 200 KB in a crafted PSD therefore makes the library allocate hundreds of MB, and the cost grows linearly with input size. This is a decompression-bomb denial of service.

## Property-Based Test

```python
@settings(max_examples=2000)
@given(st.binary(max_size=200), st.integers(1, 20), st.integers(1, 10),
       st.sampled_from([8, 16, 32]), st.sampled_from([1, 2]))
def test_decompress_garbage(data, w, h, depth, version):
    # Property: decompress returns exactly w*h*depth//8 bytes, or raises ValueError
    try:
        out = decompress(data, Compression.RLE, w, h, depth, version)
    except ValueError:
        return
    assert len(out) == w * h * depth // 8
```

The same property applied to ZIP shows that the output is never bounded by the expected length before memory is allocated:

**Failing input**: `zlib.compress(b"\x00" * (200 * 2**20))`, width=1, height=1, depth=8

## Reproducing the Bug

```python
import tracemalloc
import zlib

from psd_tools.compression import decompress
from psd_tools.constants import Compression

bomb = zlib.compress(b"\x00" * (200 * 1024 * 1024), 9)
print(len(bomb))  # 203848
tracemalloc.start()
try:
    decompress(bomb, Compression.ZIP, 1, 1, 8, 1)
except AssertionError as e:
    print(str(e)[:40])  # len=209715200, expected=1
print(tracemalloc.get_traced_memory()[1] // 2**20, "MiB")  # 437 MiB
```

## Why This Is A Bug

The caller passes `width`, `height` and `depth`, so the valid output size is known before decompression starts. Channel data comes from untrusted PSD files (`ChannelData.get_data`, `Pattern`, `ImageData`). Inflating without a limit lets roughly 1 KB of input expand to about 1 MB of memory. Also, the only check after decompression is an `assert`, which is removed under `python -O`, so oversized or undersized output is then returned silently.

## Fix

```diff
@@ def decompress(
-    elif compression == Compression.ZIP:
-        result = zlib.decompress(data)
-    else:
-        decompressed = zlib.decompress(data)
-        result = decode_prediction(decompressed, width, height, depth)
+    elif compression == Compression.ZIP:
+        result = _bounded_inflate(data, length)
+    else:
+        decompressed = _bounded_inflate(data, length)
+        result = decode_prediction(decompressed, width, height, depth)
@@
-            assert len(result) == length, "len=%d, expected=%d" % (len(result), length)
+            if len(result) != length:
+                raise ValueError("len=%d, expected=%d" % (len(result), length))
+
+
+def _bounded_inflate(data: bytes, length: int) -> bytes:
+    d = zlib.decompressobj()
+    out = d.decompress(data, length)
+    if d.unconsumed_tail or len(out) != length:
+        raise ValueError("ZIP data does not match expected size %d" % length)
+    return out
```

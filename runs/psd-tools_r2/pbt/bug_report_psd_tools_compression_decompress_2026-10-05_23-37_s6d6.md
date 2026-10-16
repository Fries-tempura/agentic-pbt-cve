# Bug Report: psd_tools.compression.decompress Unbounded ZIP Decompression (Decompression Bomb)

**Target**: `psd_tools.compression.decompress`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

For `Compression.ZIP` and `Compression.ZIP_WITH_PREDICTION`, `decompress` calls `zlib.decompress(data)` with no output bound, even though the expected output size (`width * height * depth // 8`) is known up front. A ~200 KB channel in a crafted PSD for a 1x1 layer inflates to 200 MB (peak ~440 MB RSS) before the size check runs. Scaling the payload up exhausts memory, so anyone who can supply a PSD file can trigger a denial of service.

## Property-Based Test

```python
import zlib
from hypothesis import given, settings, strategies as st
from psd_tools.compression import decompress
from psd_tools.constants import Compression

@settings(max_examples=2000)
@given(st.binary(max_size=64), st.integers(1, 8), st.integers(1, 8), st.sampled_from([8, 16, 32]),
       st.sampled_from([Compression.RLE, Compression.ZIP, Compression.ZIP_WITH_PREDICTION]), st.sampled_from([1, 2]))
def test_decompress_result_or_valueerror(payload, w, h, d, comp, v):
    if comp != Compression.RLE:
        payload = zlib.compress(payload)
    try:
        out = decompress(payload, comp, w, h, d, v)
    except (ValueError, zlib.error):
        return
    assert len(out) == w * h * d // 8
```

**Failing input**: `payload=b"\x01\x02\x03", w=1, h=1, d=8, comp=Compression.ZIP` (oversized output is fully inflated before the length check is applied)

## Reproducing the Bug

```python
import zlib, tracemalloc
from psd_tools.compression import decompress
from psd_tools.constants import Compression

bomb = zlib.compress(b"\x00" * (200 * 1024 * 1024), 9)
print(len(bomb))  # ~200 KB
tracemalloc.start()
try:
    decompress(bomb, Compression.ZIP, 1, 1, 8)
except AssertionError as e:
    print(str(e)[:40])  # len=209715200, expected=1
print(tracemalloc.get_traced_memory()[1] // 2**20, "MB peak")  # ~437 MB
```

## Why This Is A Bug

`decompress` already knows the exact number of bytes a valid channel can produce, yet it inflates attacker-controlled input with no limit. Channel data comes straight from untrusted PSD files (via `ChannelData.get_data`, `ImageData.get_data`, and `patterns.py`), so a small file can force huge memory allocations. The only check afterwards is an `assert`, which runs after the damage is done and is removed entirely under `python -O`.

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
-        else:
-            assert len(result) == length, "len=%d, expected=%d" % (len(result), length)
+        elif len(result) != length:
+            raise ValueError("len=%d, expected=%d" % (len(result), length))
+
+
+def _bounded_inflate(data: bytes, max_length: int) -> bytes:
+    d = zlib.decompressobj()
+    out = d.decompress(data, max_length)
+    if d.unconsumed_tail:
+        raise ValueError("Decompressed data exceeds expected size %d" % max_length)
+    return out
```

# Bug Report: litestar.stores.file FileStore.set silently drops long keys and get raises OSError

**Target**: `litestar.stores.file.FileStore`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

The file name is the expanded key: each non-alphanumeric character becomes 2-7 digits. Once that name exceeds the filesystem limit (usually 255 bytes), `set` swallows the `OSError` and stores nothing, and `get`, `exists` and `expires_in` raise `OSError: [Errno 63/36] File name too long`.

## Property-Based Test

```python
@settings(max_examples=50, deadline=None)
@given(k=st.text(alphabet="ab/?=&", min_size=100, max_size=400))
def test_long_key_round_trip(k):
    """CLAIM-2/CLAIM-3: long keys round-trip without raising."""
    async def body():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            await store.set(k, b"v")
            return await store.get(k)
    assert asyncio.run(body()) == b"v"
```

**Failing input**: a key of about 130 `=` characters. Each `=` expands to `61`, giving a file name over 255 bytes. Any key of 256 or more ASCII letters fails the same way.

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.set("x" * 300, b"v")
        await store.get("x" * 300)

asyncio.run(main())
```

## Why This Is A Bug

`key` is annotated `str` and no length limit is documented. `set` returns normally but discards the data, and `get` raises an undocumented `OSError` instead of returning the value or `None`. Cache keys built from long URLs/query strings readily reach this length (`/` alone expands 2x), so a request can turn a cache lookup into a 500.

## Fix

Hash the key into a fixed-length file name; see the patch in the key-collision report:

```diff
--- a/litestar/stores/file.py
+++ b/litestar/stores/file.py
@@
 import os
 import shutil
-import unicodedata
+import hashlib
 from tempfile import mkstemp
@@
 def _safe_file_name(name: str) -> str:
-    name = unicodedata.normalize("NFKD", name)
-    return "".join(c if c.isalnum() else str(ord(c)) for c in name)
+    return hashlib.sha256(name.encode("utf-8")).hexdigest()
```

# Bug Report: litestar.stores.file FileStore maps distinct keys to the same file

**Target**: `litestar.stores.file.FileStore`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`_safe_file_name` replaces every non-alphanumeric character with its decimal code point and also applies NFKD normalisation. Because of this, many distinct keys map to the same file name: `"!"`/`"33"`, `"a/b"`/`"a47b"`, `"ﬁ"`/`"fi"`. Writing one key silently overwrites the other, and reading one returns the other's value.

## Property-Based Test

```python
@settings(max_examples=300, deadline=None)
@given(ks=st.lists(st.text(alphabet="a3!ﬁf", min_size=1, max_size=4), unique=True, min_size=2, max_size=8))
def test_distinct_keys_do_not_collide(ks):
    """CLAIM-1: distinct keys keep distinct values."""
    async def body():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            for i, k in enumerate(ks):
                await store.set(k, str(i).encode())
            return {k: await store.get(k) for k in ks}
    got = asyncio.run(body())
    assert got == {k: str(i).encode() for i, k in enumerate(ks)}
```

**Failing input**: `ks=['!', '33']`

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.set("!", b"secret")
        await store.set("33", b"attacker")
        assert await store.get("!") == b"secret"

asyncio.run(main())
```

## Why This Is A Bug

`FileStore` is documented as a key/value store, and `get` is documented to return "the value associated with `key`". With these collisions, a value stored under one key can be read, overwritten, deleted or `exists()`-checked through a different key. Litestar uses stores for server-side sessions and response caching. An attacker who controls a key (for example a cache key built from a request path, where `/` becomes `47`) can poison or read another key's entry.

## Fix

Use an injective, fixed-length encoding of the key. A cryptographic hash also removes the file-name length problem:

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

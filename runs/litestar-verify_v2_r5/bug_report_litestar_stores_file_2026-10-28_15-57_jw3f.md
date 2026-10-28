# Bug Report: litestar.stores.file FileStore.expires_in returns -1 instead of None when no expiry is set

**Target**: `litestar.stores.file.FileStore`
**Severity**: Low
**Bug Type**: Contract
**Date**: 2026-10-28

## Summary

The docstring says `expires_in` returns `None` if "no expiry time was set", but for a key stored without expiry it returns `-1`. That value comes from `StorageObject.expires_in`.

## Property-Based Test

```python
@given(k=keys)
@settings(max_examples=20, deadline=None)
def test_expires_in_none(k):
    """CLAIM-4: no expiry -> expires_in returns None."""
    async def body():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            await store.set(k, b"v")
            return await store.expires_in(k)
    assert asyncio.run(body()) is None
```

**Failing input**: `k='0'`

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.set("k", b"v")
        assert await store.expires_in("k") is None

asyncio.run(main())
```

## Why This Is A Bug

file.py:175 and base.py:78 both document "If no such `key` exists or no expiry time was set, return `None`". A caller that checks `if ttl is not None` would treat `-1` as an expiry time.

## Fix

```diff
         if storage_obj := await self._load_from_path(self._path_from_key(key)):
-            return storage_obj.expires_in
+            return storage_obj.expires_in if storage_obj.expires_at else None
         return None
```

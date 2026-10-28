# Bug Report: litestar.stores.file.FileStore.expires_in returns -1 instead of None when no expiry was set

**Target**: `litestar.stores.file.FileStore.expires_in`
**Severity**: Low
**Bug Type**: Contract
**Date**: 2026-10-28

## Summary

The docstring says "If no such `key` exists or no expiry time was set, return `None`". For a key set without expiry, the method returns `-1`, because it passes through `StorageObject.expires_in`.

## Property-Based Test

```python
@given(k=keys, v=st.binary())
def test_expires_in_none_without_expiry(k, v):
    """CLAIM-2: expires_in is None when no expiry was set."""
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(k, v)
            return await s.expires_in(k)
    assert asyncio.run(go()) is None
```

**Failing input**: `k='0', v=b''`

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        s = FileStore(Path(d))
        await s.set("k", b"v")
        assert await s.expires_in("k") is None, await s.expires_in("k")

asyncio.run(main())
```

## Why This Is A Bug

The return value contradicts the documented contract (`int | None`, with `None` for "no expiry"). A caller that checks `if ttl is None` treats a key with no expiry as one that expired 1 second ago. MemoryStore and RedisStore behave the same way, so the fix could be in the code or in the docstrings.

## Fix

```diff
         if storage_obj := await self._load_from_path(self._path_from_key(key)):
-            return storage_obj.expires_in
+            return storage_obj.expires_in if storage_obj.expires_at else None
         return None
```

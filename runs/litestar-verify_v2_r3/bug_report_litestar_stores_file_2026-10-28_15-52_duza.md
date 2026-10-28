# Bug Report: litestar.stores.file.FileStore.expires_in returns -1 instead of None when no expiry is set

**Target**: `litestar.stores.file.FileStore.expires_in`
**Severity**: Low
**Bug Type**: Contract
**Date**: 2026-10-28

## Summary

The docstring says expires_in returns `None` when "no expiry time was set". For a key stored without an expiry, it returns `-1`, the sentinel from `StorageObject.expires_in`.

## Property-Based Test

```python
@settings(max_examples=300, deadline=None)
@given(k=st.text(min_size=1, max_size=20))
def test_expires_in_none(k):
    """CLAIM-4: no expiry set -> expires_in is None."""
    async def body(store):
        await store.set(k, b"x")
        return await store.expires_in(k)
    assert run(body) is None
```

**Failing input**: `k='0'`

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main(d):
    s = FileStore(Path(d))
    await s.set("k", b"v")
    assert await s.expires_in("k") is None, await s.expires_in("k")

with tempfile.TemporaryDirectory() as d:
    asyncio.run(main(d))
```

## Why This Is A Bug

The code contradicts its documented return value. MemoryStore and RedisStore behave the same way (they return -1), so the docstring may be what's wrong. Either way, the code and the docs disagree.

## Fix

```diff
         if storage_obj := await self._load_from_path(self._path_from_key(key)):
-            return storage_obj.expires_in
+            return storage_obj.expires_in if storage_obj.expires_at else None
         return None
```

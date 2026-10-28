# Bug Report: litestar.stores.file.FileStore.delete_expired crashes when a child namespace exists

**Target**: `litestar.stores.file.FileStore.delete_expired`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

`with_namespace` stores child data in a subdirectory of the parent path. `delete_expired` on the parent iterates `self.path.iterdir()` and calls `read_bytes()` on every entry, including the child directory. That raises `IsADirectoryError`. Expired items in the child namespace are also never removed, even though `NamespacedStore` documents that bulk actions on a parent affect all children.

## Property-Based Test

```python
def test_delete_expired_with_namespace():
    """CLAIM-4: delete_expired on the parent works with child namespaces and removes their expired items."""
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            child = s.with_namespace("child")
            await child.set("k", b"v", expires_in=1)
            await asyncio.sleep(1.1)
            await s.delete_expired()
            return (Path(d) / "child" / "k").exists()
    assert asyncio.run(go()) is False
```

**Failing input**: any parent store that has at least one child namespace

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        s = FileStore(Path(d))
        await s.with_namespace("child").set("k", b"v")
        await s.delete_expired()

asyncio.run(main())
```

## Why This Is A Bug

`delete_expired` documents no exception, and `NamespacedStore` says "Bulk actions on a parent namespace should affect all child namespaces". Litestar's `StoreRegistry` creates namespaced FileStores this way, so a periodic cleanup on the root store crashes.

## Fix

```diff
     async def delete_expired(self) -> None:
         async for file in self.path.iterdir():
+            if await file.is_dir():
+                await FileStore(file).delete_expired()
+                continue
             wrapper = await self._load_from_path(file)
```

# Bug Report: litestar.stores.file.FileStore namespaces are not isolated, and delete_expired crashes when they exist

**Target**: `litestar.stores.file.FileStore.with_namespace`, `FileStore.delete_expired`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

`with_namespace(ns)` stores the child under `self.path / ns`, in the same directory as the parent's key files. Two things go wrong:
1. Once a child namespace exists, `parent.delete_expired()` iterates over the namespace directory too, calls `read_bytes()` on it, and raises `IsADirectoryError`.
2. If the parent holds a key whose file name equals `ns` (alphanumeric keys map to themselves), `child.set(...)` raises `FileExistsError`.

## Property-Based Test

```python
@settings(max_examples=100, deadline=None)
@given(ns=st.text(alphabet="ab0", min_size=1, max_size=3), k=st.text(alphabet="ab0", min_size=1, max_size=3))
def test_namespace_isolation(ns, k):
    """CLAIM-3: parent and child namespaces are isolated; parent bulk ops work with children."""
    with tempfile.TemporaryDirectory() as d:
        parent = FileStore(Path(d) / "s")
        child = parent.with_namespace(ns)
        async def go():
            await parent.set(k, b"parent")
            await child.set(k, b"child")
            p, c = await parent.get(k), await child.get(k)
            await parent.delete_expired()
            return p, c
        assert run(go()) == (b"parent", b"child")
```

**Failing input**: `ns='0', k='a'` (IsADirectoryError); `ns='0', k='0'` (FileExistsError)

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    parent = FileStore(Path(tempfile.mkdtemp()))
    child = parent.with_namespace("sessions")
    await child.set("k", b"v")
    await parent.delete_expired()  # IsADirectoryError

    parent2 = FileStore(Path(tempfile.mkdtemp()))
    await parent2.set("cache", b"v")
    await parent2.with_namespace("cache").set("k", b"v")  # FileExistsError

asyncio.run(main())
```

## Why This Is A Bug

`NamespacedStore` documents: "Bulk actions on a parent namespace should affect all child namespaces, whereas other operations on all namespaces should be isolated." Instead, `delete_expired` on the parent crashes, and a parent key blocks writes to the child namespace.

## Fix

```diff
     async def delete_expired(self) -> None:
         async for file in self.path.iterdir():
+            if await file.is_dir():
+                await FileStore(file).delete_expired()
+                continue
             wrapper = await self._load_from_path(file)
```

To stop key and namespace names from colliding, put key files and namespace directories in separate name spaces. For example, prefix key file names (`"k_" + safe_name`), or store children under a `"ns_"`-prefixed subdirectory.

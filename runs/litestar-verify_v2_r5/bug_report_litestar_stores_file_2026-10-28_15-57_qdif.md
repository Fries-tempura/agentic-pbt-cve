# Bug Report: litestar.stores.file FileStore.get raises IsADirectoryError for keys that map to a directory

**Target**: `litestar.stores.file.FileStore`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

Two kinds of key make `_path_from_key` return a directory:
- The empty key `""` maps to the store root.
- An alphanumeric key equal to a child namespace name maps to that namespace's sub-directory.

`get` (and `expires_in`) then raise `IsADirectoryError`. `set` for such a key silently does nothing, and `exists` wrongly returns `True`.

## Property-Based Test

```python
@settings(max_examples=100, deadline=None)
@given(ns=st.text(alphabet="ab12", min_size=1, max_size=3), k=keys)
def test_namespace_isolation(ns, k):
    """CLAIM-5: values in a child namespace are not visible from the parent."""
    async def body():
        with tempfile.TemporaryDirectory() as d:
            parent = FileStore(Path(d))
            child = parent.with_namespace(ns)
            await child.set(k, b"child")
            return await parent.get(ns), await parent.exists(ns)
    got, ex = asyncio.run(body())
    assert got is None and ex is False
```

**Failing input**: `ns='1', k='0'` (also `test_no_crash(k='')`)

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.with_namespace("sessions").set("k", b"v")
        print(await store.exists("sessions"))
        await store.get("sessions")

asyncio.run(main())
```

## Why This Is A Bug

`NamespacedStore` documents that operations on different namespaces "should be isolated". Here, a parent key collides with a child namespace's directory and `get` raises an undocumented exception. The empty string is a valid `str` key and fails the same way.

## Fix

Keep key files and namespace directories in disjoint name spaces. For example, hash keys (as in the collision report), or put a prefix on key file names that namespace names, which must be alphanumeric, can never produce:

```diff
     def _path_from_key(self, key: str) -> Path:
-        return self.path / _safe_file_name(key)
+        return self.path / f"_{_safe_file_name(key)}"
```

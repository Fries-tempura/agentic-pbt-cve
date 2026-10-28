# Bug Report: litestar.stores.file.FileStore key equal to a child namespace name breaks the parent store

**Target**: `litestar.stores.file.FileStore.with_namespace`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

`with_namespace(ns)` stores child data in the subdirectory `path/ns`, and the parent stores key `ns` in the file `path/ns`. When both exist, `set("ns", ...)` silently fails (the error is swallowed), and `get("ns")` raises `IsADirectoryError`.

## Property-Based Test

```python
@settings(max_examples=300, deadline=None)
@given(ns=st.text(alphabet="abc01", min_size=1, max_size=3), k=st.text(alphabet="abc01", min_size=1, max_size=3))
def test_namespace_isolated(ns, k):
    """CLAIM-5: child namespace ops don't affect parent keys."""
    async def body(store):
        child = store.with_namespace(ns)
        await store.set("seed", b"s")
        await child.set("x", b"child")
        await store.set(k, b"parent")
        return await store.get(k)
    assert run(body) == b"parent"
```

**Failing input**: `ns='0', k='0'`

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main(d):
    s = FileStore(Path(d))
    await s.with_namespace("ns").set("k", b"c")
    await s.set("ns", b"parent")
    await s.get("ns")

with tempfile.TemporaryDirectory() as d:
    asyncio.run(main(d))
```

```
IsADirectoryError: [Errno 21] Is a directory: '.../ns'
```

## Why This Is A Bug

`NamespacedStore` documents that operations on different namespaces "should be isolated". Here, a child namespace makes a parent key unwritable and unreadable. Litestar uses the namespaces "sessions", "response_cache", and others on the root store, so a parent key with one of those names fails.

## Fix

Keep key files and namespace directories apart, for example by giving key files a suffix or prefix that `with_namespace` cannot produce (namespaces must be alphanumeric):

```diff
     def _path_from_key(self, key: str) -> Path:
-        return self.path / _safe_file_name(key)
+        return self.path / f"{_safe_file_name(key)}.store"
```

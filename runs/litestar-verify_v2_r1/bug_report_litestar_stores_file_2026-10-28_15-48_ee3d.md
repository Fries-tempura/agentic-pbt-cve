# Bug Report: litestar.stores.file.FileStore distinct keys collide on the same file

**Target**: `litestar.stores.file.FileStore` / `_safe_file_name`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`_safe_file_name` replaces each non-alphanumeric character with its decimal `ord()` and adds no delimiter or escape, so the mapping is not injective: `"-"` and `"45"` (or `"a-"` and `"a45"`) map to the same file. Writing one key silently overwrites the other, and `get`, `exists`, `delete` operate on the wrong entry. NFKD normalisation makes this worse (for example `"ﬁ"` and `"fi"` collide). If keys come partly from user input (for example response-cache keys built from the request path), an attacker can read or poison another key's entry.

## Property-Based Test

```python
ALPHA = "a456-."  # "-"->45, "."->46
keys = st.text(alphabet=ALPHA, min_size=1, max_size=4)

@settings(max_examples=300, deadline=None)
@given(ks=st.lists(keys, unique=True, min_size=2, max_size=12))
def test_distinct_keys_independent(ks):
    """CLAIM-1: each distinct key retrieves exactly its own value."""
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d) / "s")
        async def go():
            for i, k in enumerate(ks):
                await store.set(k, str(i).encode())
            return [await store.get(k) for k in ks]
        assert run(go()) == [str(i).encode() for i in range(len(ks))]
```

**Failing input**: `ks=['-', '45']`

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    store = FileStore(Path(tempfile.mkdtemp()))
    await store.set("a-", b"one")
    await store.set("a45", b"two")
    assert await store.get("a-") == b"one", await store.get("a-")

asyncio.run(main())
```

## Why This Is A Bug

`get` is documented to return "The value associated with ``key``". Here `get("a-")` returns `b"two"`, which was stored under a different key. Deleting `"a45"` also makes `"a-"` disappear.

## Fix

Use a mapping that cannot collide, such as a hash of the exact key bytes (no normalisation):

```diff
-import unicodedata
+import hashlib
@@
 def _safe_file_name(name: str) -> str:
-    name = unicodedata.normalize("NFKD", name)
-    return "".join(c if c.isalnum() else str(ord(c)) for c in name)
+    return hashlib.sha256(name.encode("utf-8")).hexdigest()
```

This also keeps every file name a fixed 64 characters, which fixes the separate long-key bug.

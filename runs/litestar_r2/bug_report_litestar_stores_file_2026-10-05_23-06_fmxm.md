# Bug Report: litestar.stores.file FileStore maps distinct keys to the same file

**Target**: `litestar.stores.file.FileStore` / `_safe_file_name`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`_safe_file_name` replaces every non-alphanumeric character with its decimal code point (`str(ord(c))`) and joins the pieces with no delimiter or escaping, so the mapping isn't injective. Distinct keys such as `"session:"` and `"session58"` resolve to the same file. Setting one key silently overwrites the other, and `get`/`delete`/`exists` act on the wrong entry. NFKD normalization adds more collisions (for example, `"ﬁ"` and `"fi"`).

## Property-Based Test

```python
import asyncio, tempfile
from pathlib import Path
from hypothesis import given, strategies as st
from litestar.stores.file import FileStore

alnum = st.text(st.characters(categories=["Ll", "Lu", "Nd"], max_codepoint=127), max_size=10)
special = st.characters(min_codepoint=32, max_codepoint=126).filter(lambda c: not c.isalnum())

@given(alnum, special, alnum)
def test_distinct_keys_isolated(prefix, c, suffix):
    k1 = prefix + c + suffix
    k2 = prefix + str(ord(c)) + suffix
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(k1, b"v1")
            await s.set(k2, b"v2")
            return await s.get(k1)
    assert asyncio.run(go()) == b"v1"
```

**Failing input**: `prefix='', c=':', suffix=''` (i.e. keys `':'` and `'58'`)

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.set("session:", b"alice")
        await store.set("session58", b"mallory")
        print(await store.get("session:"))  # b'mallory'

asyncio.run(main())
```

## Why This Is A Bug

A key/value store has to keep distinct keys separate. `FileStore` is used as a backend for server-side sessions and response caching. Cache keys are built from request paths and query strings that clients control, so a client can choose a key whose filename matches another entry's. That lets the client read or poison another entry, such as a cached response from a different URL. The in-memory and Redis stores don't have this problem, so the backends don't behave the same way.

## Fix

Use an injective encoding. Hashing also bounds the filename length:

```diff
-import unicodedata
+import hashlib
@@
 def _safe_file_name(name: str) -> str:
-    name = unicodedata.normalize("NFKD", name)
-    return "".join(c if c.isalnum() else str(ord(c)) for c in name)
+    return hashlib.sha256(name.encode("utf-8")).hexdigest()
```

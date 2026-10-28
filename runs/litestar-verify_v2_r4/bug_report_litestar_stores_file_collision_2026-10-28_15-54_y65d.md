# Bug Report: litestar.stores.file.FileStore distinct keys collide and overwrite each other

**Target**: `litestar.stores.file.FileStore` (`_safe_file_name`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`_safe_file_name` turns every non-alphanumeric character into the decimal digits of its code point, without a delimiter, and runs NFKD normalization first. So different keys can map to the same file name: `"a-"`/`"a45"`, `"user:1"`/`"user581"`, `"1"`/`"①"`. When that happens, `set` on one key silently overwrites the value of the other, and `get`, `delete` and `exists` act on the wrong entry.

## Property-Based Test

```python
KEY_ALPHA = "ab0145-_/.: ﬁ①"
keys = st.text(alphabet=KEY_ALPHA, min_size=1, max_size=6)

@settings(max_examples=300, deadline=None)
@given(ks=st.lists(keys, unique=True, min_size=2, max_size=8))
def test_distinct_keys_do_not_clobber(ks):
    """CLAIM-1: distinct keys keep their own values."""
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            for i, k in enumerate(ks):
                await s.set(k, str(i).encode())
            return [await s.get(k) for k in ks]
    assert asyncio.run(go()) == [str(i).encode() for i in range(len(ks))]
```

**Failing input**: `ks=['1', '①']` (also `['a-', 'a45']`)

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        s = FileStore(Path(d))
        await s.set("user:1", b"alice-secret")
        await s.set("user581", b"mallory")
        assert await s.get("user:1") == b"alice-secret", await s.get("user:1")

asyncio.run(main())
```

## Why This Is A Bug

`Store.get` is documented to return "The value associated with `key`". With FileStore, writing one key changes the value returned for a different key. FileStore backs sessions, response caching and rate limiting. If an attacker controls part of a key (for example a URL path or query string in a cache key), they can pick a colliding key and overwrite or read another key's entry. That is cache poisoning or cross-entry data leakage.

## Fix

Use an injective, filesystem-safe encoding of the key instead of digit concatenation, for example a hash:

```diff
-import unicodedata
+import hashlib
@@
 def _safe_file_name(name: str) -> str:
-    name = unicodedata.normalize("NFKD", name)
-    return "".join(c if c.isalnum() else str(ord(c)) for c in name)
+    return hashlib.sha256(name.encode("utf-8")).hexdigest()
```

# Bug Report: litestar.stores.file FileStore maps distinct keys to the same file

**Target**: `litestar.stores.file.FileStore` (`_safe_file_name`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`FileStore` turns a key into a file name with `_safe_file_name`. That function keeps alphanumerics, replaces every other character with its decimal `ord()`, and first applies NFKD normalisation. The mapping is not injective, so distinct keys share one file. Setting one key overwrites another key's value, and `get`, `exists` and `delete` act on the wrong entry.

## Property-Based Test

```python
ALPHABET = "a0123456789-./_²ﬁfi"
keys = st.text(alphabet=ALPHABET, min_size=1, max_size=4)

@settings(max_examples=1000, deadline=None)
@given(ks=st.lists(keys, unique=True, min_size=2, max_size=12))
def test_distinct_keys_keep_values(ks):
    """CLAIM-1: distinct keys each keep their own value."""
    async def go():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            for i, k in enumerate(ks):
                await store.set(k, str(i).encode())
            return [await store.get(k) for k in ks]
    got = asyncio.run(go())
    assert got == [str(i).encode() for i in range(len(ks))]
```

**Failing input**: `ks=['2', '²']` (`test_exists_only_set_key` also fails, with `k1='²', others=['2']`)

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.set("GET/users/alice-profile", b"alice's private page")
        assert await store.get("GET/users/alice45profile") is None  # fails: returns alice's data

        await store.set("2", b"two")
        await store.set("²", b"superscript")
        assert await store.get("2") == b"two"  # fails: b"superscript"

asyncio.run(main())
```

## Why This Is A Bug

`Store` is documented as a key/value store: `get(key)` returns "the value associated with ``key`` if it exists" and `exists` reports whether "a given ``key`` exists". Here, writing one key changes what a different key returns. Two kinds of collision cause this:
- **ord substitution**: `"-"` → `"45"`, so `"a-b"` and `"a45b"` collide. The same happens for any non-alphanumeric character and its decimal code.
- **NFKD**: `"²"` ≡ `"2"`, `"ﬁ"` ≡ `"fi"`, `"ａ"` ≡ `"a"`, and so on.

These keys come from users. `default_cache_key_builder` in `litestar/config/response_cache.py` builds keys as `method + url.path + query`. With `FileStore` as the response-cache backend, `GET /users/alice45profile` is served the cached response of `GET /users/alice-profile`. An attacker can therefore read another route's cached response or poison it. Session and rate-limit keys stored in a `FileStore` are open to the same collisions.

## Fix

```diff
--- a/litestar/stores/file.py
+++ b/litestar/stores/file.py
@@
+import hashlib
 import os
 import shutil
-import unicodedata
@@
 def _safe_file_name(name: str) -> str:
-    name = unicodedata.normalize("NFKD", name)
-    return "".join(c if c.isalnum() else str(ord(c)) for c in name)
+    return hashlib.sha256(name.encode("utf-8")).hexdigest()
```

(Any injective encoding works, for example `name.encode("utf-8").hex()`. Hashing also keeps file names to a fixed length. Existing on-disk entries are invalidated once, which is acceptable for a cache store.)

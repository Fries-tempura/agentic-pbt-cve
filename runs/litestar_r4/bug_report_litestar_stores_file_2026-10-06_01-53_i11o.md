# Bug Report: litestar.stores.file FileStore maps distinct keys to the same file

**Target**: `litestar.stores.file.FileStore` / `_safe_file_name`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`_safe_file_name` replaces each non-alphanumeric character with its decimal code point (and applies NFKD normalization), so the key-to-filename mapping is not injective. Distinct keys such as `":"` and `"58"`, `"-"` and `"45"`, `"a/b"` and `"a47b"`, or `"ﬁ"` and `"fi"` share one file. Setting one key silently overwrites the other, and `get`/`delete`/`exists` on one key read or affect the other key's data.

## Property-Based Test

```python
import asyncio, tempfile
from pathlib import Path
from hypothesis import given, settings, assume, strategies as st
from litestar.stores.file import FileStore

ascii_keys = st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=20)

@st.composite
def key_pairs(draw):
    k1 = draw(ascii_keys)
    k2 = "".join(c if c.isalnum() else str(ord(c)) for c in k1)
    assume(k1 != k2)
    return k1, k2

@settings(max_examples=200, deadline=None)
@given(key_pairs(), st.binary(min_size=1), st.binary(min_size=1))
def test_distinct_keys_do_not_overwrite_each_other(pair, v1, v2):
    k1, k2 = pair
    assume(v1 != v2)
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        async def go():
            await store.set(k1, v1)
            await store.set(k2, v2)
            return await store.get(k1)
        assert asyncio.run(go()) == v1
```

**Failing input**: `pair=(':', '58'), v1=b'\x00', v2=b'\t'`

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    store = FileStore(Path(tempfile.mkdtemp()))
    await store.set(":", b"user-A-session")
    await store.set("58", b"user-B-session")
    print(await store.get(":"))

asyncio.run(main())
```

Output: `b'user-B-session'`

## Why This Is A Bug

A key/value store must keep distinct keys independent. `FileStore` backs server-side sessions, response caching and rate limiting. When keys collide, one entry can overwrite another, or a lookup can return another key's data (e.g. another client's session or cached response). The encoding is ambiguous because the digits it emits for a replaced character can't be told apart from literal digits in the key. NFKD normalization also merges distinct keys (`"ﬁ"`/`"fi"`, full-width vs ASCII). A related issue: long keys produce file names over the OS limit, so `set` silently drops the value (the `OSError` is swallowed) and `get` raises `OSError: File name too long`.

## Fix

Use an injective, fixed-length encoding of the key, e.g. a cryptographic hash:

```diff
--- a/litestar/stores/file.py
+++ b/litestar/stores/file.py
@@
 import os
 import shutil
-import unicodedata
+import hashlib
 from tempfile import mkstemp
@@
 def _safe_file_name(name: str) -> str:
-    name = unicodedata.normalize("NFKD", name)
-    return "".join(c if c.isalnum() else str(ord(c)) for c in name)
+    return hashlib.sha256(name.encode("utf-8")).hexdigest()
```

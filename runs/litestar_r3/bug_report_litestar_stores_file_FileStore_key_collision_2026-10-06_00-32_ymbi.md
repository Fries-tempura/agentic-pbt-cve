# Bug Report: litestar.stores.file FileStore maps distinct keys to the same file

**Target**: `litestar.stores.file.FileStore` / `_safe_file_name`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`FileStore` turns a key into a filename with `_safe_file_name`. That function keeps alphanumeric characters and replaces every other character with its decimal code point, with no delimiter or escape. It also applies NFKD normalization. As a result, different keys can produce the same filename, so they read and overwrite the same entry. For example, `"-"` and `"45"` both become `45`, and `"ﬁ"` and `"fi"` both become `fi`. On case-insensitive filesystems such as default macOS APFS or Windows NTFS, `"N"` and `"n"` also share an entry.

## Property-Based Test

```python
import tempfile
from pathlib import Path

import anyio
from hypothesis import assume, given, settings, strategies as st

from litestar.stores.file import FileStore

ascii_keys = st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=10)


@settings(max_examples=2000, deadline=None)
@given(ascii_keys, ascii_keys)
def test_distinct_ascii_keys_are_independent(k1, k2):
    assume(k1 != k2)

    async def main():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            await store.set(k1, b"one")
            await store.set(k2, b"two")
            return await store.get(k1)

    assert anyio.run(main) == b"one", (k1, k2)
```

**Failing input**: `k1='N', k2='n'` on macOS, a case-insensitive filesystem. Other failing pairs on any filesystem: `k1='-', k2='45'`, and `k1='ﬁ', k2='fi'`.

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.set("-", b"secret-of-user-A")
        await store.set("45", b"data-of-user-B")
        print(await store.get("-"))   # b'data-of-user-B'
        await store.set("\ufb01", b"x")
        print(await store.get("fi"))  # b'x'

asyncio.run(main())
```

## Why This Is A Bug

`Store` is documented as a key/value store, so distinct keys should refer to distinct values. `FileStore` is used for server-side sessions, response caching and rate limiting, and the keys there often contain user-controlled data. When two keys collide, one entry can silently overwrite or read another. This can mix up sessions or cache entries, which risks data corruption and leaking data between users. The other `Store` backends (memory and Redis) treat each key exactly, so `FileStore` behaves inconsistently with them.

## Fix

Use an encoding that is injective and works on case-insensitive filesystems. A hash of the raw key does this and also keeps filenames within length limits:

```diff
--- a/litestar/stores/file.py
+++ b/litestar/stores/file.py
@@
+import hashlib
 import os
 import shutil
-import unicodedata
 from tempfile import mkstemp
@@
 def _safe_file_name(name: str) -> str:
-    name = unicodedata.normalize("NFKD", name)
-    return "".join(c if c.isalnum() else str(ord(c)) for c in name)
+    return hashlib.sha256(name.encode("utf-8")).hexdigest()
```

This changes existing on-disk filenames, so entries written by older versions become unreachable. That is acceptable for a cache or session store.

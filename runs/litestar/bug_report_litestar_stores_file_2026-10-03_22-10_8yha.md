# Bug Report: litestar.stores.file.FileStore Distinct Keys Collide Into The Same File

**Target**: `litestar.stores.file.FileStore` (`_safe_file_name`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-03

## Summary

`_safe_file_name` maps each non-alphanumeric character to its decimal code point without any
escaping, so distinct keys collapse onto the same filename (`"-"` and `"45"` both become `"45"`).
Two different keys then share one stored value: writing one silently overwrites the other, reading
one returns the other's data, and deleting one deletes the other. With the default response-cache
key builder this is reachable from a plain HTTP request, so one URL can be served another URL's
cached response.

## Property-Based Test

```python
import string
import tempfile
from pathlib import Path

import anyio
from hypothesis import given, settings
from hypothesis import strategies as st

from litestar.stores.file import FileStore, _safe_file_name

ALPHABET = "0123456789ab-_/:."
keys = st.text(alphabet=ALPHABET, min_size=1, max_size=4)


def make_store():
    return FileStore(Path(tempfile.mkdtemp()))


@settings(max_examples=2000)
@given(ks=st.lists(keys, unique=True, min_size=2, max_size=8))
def test_safe_file_name_injective_over_set(ks):
    """Distinct keys must produce distinct filenames."""
    encoded = [_safe_file_name(k) for k in ks]
    assert len(set(encoded)) == len(ks), f"collision among {ks!r} -> {encoded!r}"


@settings(max_examples=3000)
@given(k1=keys, k2=keys)
def test_distinct_keys_are_isolated(k1, k2):
    if k1 == k2:
        return
    store = make_store()

    async def run():
        await store.set(k1, b"value-one")
        await store.set(k2, b"value-two")
        assert await store.get(k1) == b"value-one"

    anyio.run(run)


@settings(max_examples=3000)
@given(k1=keys, k2=keys)
def test_delete_does_not_affect_other_keys(k1, k2):
    if k1 == k2:
        return
    store = make_store()

    async def run():
        await store.set(k1, b"payload")
        await store.delete(k2)
        assert await store.exists(k1) is True

    anyio.run(run)
```

**Failing input**: `ks=['-', '45']` (and `k1='-', k2='45'`; `k1='.', k2='46'`)

```
AssertionError: collision among ['-', '45'] -> ['45', '45']
AssertionError: assert b'value-two' == b'value-one'   # test_distinct_keys_are_isolated(k1='-', k2='45')
assert False is True                                  # test_delete_does_not_affect_other_keys(k1='.', k2='46')
```

## Reproducing the Bug

```python
import tempfile
from pathlib import Path

import anyio

from litestar.stores.file import FileStore

store = FileStore(Path(tempfile.mkdtemp()))


async def main():
    await store.set("-", b"value-one")
    await store.set("45", b"value-two")
    assert await store.get("-") == b"value-one", await store.get("-")


anyio.run(main)
```

Reachable over HTTP through the default response cache, where the cache key is
`method + url.path + urlencode(query)`:

```python
import tempfile
from pathlib import Path

from litestar import get
from litestar.stores.file import FileStore
from litestar.testing import create_test_client


@get("/{item:str}", cache=True)
async def handler(item: str) -> str:
    return f"response for {item}"


store = FileStore(Path(tempfile.mkdtemp()))

with create_test_client([handler], stores={"response_cache": store}) as client:
    print(client.get("/a-b").text)
    print(client.get("/a45b").text)
```

Output:

```
response for a-b
response for a-b
```

`GET /a45b` is served the cached body of `GET /a-b`.

## Why This Is A Bug

`Store.get` is documented to return "The value associated with ``key``", and `Store.delete` to
delete "Key of the value to delete". Both guarantees require the key-to-file mapping to be
injective. It is not:

- `"-"` → `"45"` and `"45"` → `"45"` — every non-alphanumeric character is replaced by its
  unescaped decimal code point, which is itself a valid alphanumeric key fragment.
- `unicodedata.normalize("NFKD", ...)` adds a second collision class: `"①"` and `"1"` both
  encode to `"1"`, as do `"ﬁ"` and `"fi"`.

Because `FileStore` backs litestar's response cache, server-side sessions and rate limiting, a
collision means one client can read or clobber another entry — cached response leakage between
distinct URLs, and session/rate-limit entries overwriting each other.

## Fix

Use an injective encoding. Hashing the key is the simplest option and also bounds the filename
length (the current scheme can exceed the OS filename limit) and keeps the name ASCII (`str.isalnum()`
is true for many non-ASCII characters, which the current scheme passes through unescaped). Nothing
in the module recovers a key from a filename — `_path_from_key` is the only caller, and
`delete_expired` iterates files and reads their contents — so a one-way mapping is safe.

```diff
--- a/litestar/stores/file.py
+++ b/litestar/stores/file.py
@@ -1,8 +1,8 @@
 from __future__ import annotations
 
+import hashlib
 import os
 import shutil
-import unicodedata
 from tempfile import mkstemp
 from typing import TYPE_CHECKING
 
@@ -20,8 +20,7 @@ if TYPE_CHECKING:
 
 
 def _safe_file_name(name: str) -> str:
-    name = unicodedata.normalize("NFKD", name)
-    return "".join(c if c.isalnum() else str(ord(c)) for c in name)
+    return hashlib.sha256(name.encode("utf-8")).hexdigest()
```

If human-readable filenames are required instead, escape the escape character, e.g.
`"".join(c if c.isalnum() and c.isascii() else f"_{ord(c)}_" for c in name)` with `_` itself
escaped — but that does not bound the filename length.

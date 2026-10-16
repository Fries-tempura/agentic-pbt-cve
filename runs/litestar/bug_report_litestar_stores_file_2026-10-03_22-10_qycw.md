# Bug Report: litestar.stores.file.FileStore Long Keys Silently Lose Data And Crash get()

**Target**: `litestar.stores.file.FileStore` (`set`, `get`, `_write_sync`)
**Severity**: Medium
**Bug Type**: Crash

**Date**: 2026-10-03

## Summary

`_safe_file_name` expands every non-alphanumeric character to 2–3 decimal digits, so a key of
~100 characters can produce a filename longer than the 255-byte OS limit. `set()` swallows the
resulting `OSError` in `_write_sync` (`except OSError: pass`) and silently stores nothing, while
`get()` only catches `FileNotFoundError` and propagates the `OSError`. With the default response
cache key builder this turns an ordinary long URL into an unhandled HTTP 500.

## Property-Based Test

```python
import string
import tempfile
from pathlib import Path
from urllib.parse import urlencode

import anyio
from hypothesis import given, settings
from hypothesis import strategies as st

from litestar.stores.file import FileStore

word = st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=8)
segments = st.lists(word, min_size=1, max_size=6)
params = st.lists(st.tuples(word, word), max_size=20)


@st.composite
def cache_keys(draw):
    """Mirror of litestar.config.response_cache.default_cache_key_builder."""
    path = "/" + "/".join(draw(segments))
    query = sorted(draw(params), key=lambda x: x[0])
    return "GET" + path + urlencode(query, doseq=True)


def make_store():
    return FileStore(Path(tempfile.mkdtemp()))


@settings(max_examples=500)
@given(key=cache_keys(), value=st.binary(min_size=1, max_size=16))
def test_set_get_round_trip(key, value):
    store = make_store()

    async def run():
        await store.set(key, value)
        assert await store.get(key) == value, f"lost value for {len(key)}-char key"

    anyio.run(run)


@settings(max_examples=500)
@given(key=cache_keys())
def test_get_returns_none_for_unset_key(key):
    """get() is documented to return None when the key does not exist."""
    store = make_store()

    async def run():
        assert await store.get(key) is None

    anyio.run(run)
```

**Failing input**:

```
test_set_get_round_trip(
    key='GET/00/000/0000/000000000=0&0=0&0=0&0=0&0=0&0=00000000&0=00000000&00=00&00=000&00=0000&00=000000&00=00000000&000=00000&0000=00000000&00000=00000000&000000=0000000&0000000=00000000&00000000=00000000&00000000=00000000',
)
AssertionError: lost value for 209-char key

test_get_returns_none_for_unset_key(
    key='GET/0/00/0000/000000000=0&0=000&0=00000000&00=00000&00=00000000&00=00000000&000=00000000&000=00000000&000=00000000&0000=00000000&0000=00000000&00000=00000&00000=00000000&000000=00000000&00000000=00000000&00000000=00000000',
)
OSError: [Errno 63] File name too long
```

## Reproducing the Bug

```python
import tempfile
from pathlib import Path

import anyio

from litestar.stores.file import FileStore

store = FileStore(Path(tempfile.mkdtemp()))
key = "-" * 200


async def main():
    await store.set(key, b"data")
    print(await store.get(key))


anyio.run(main)
```

```
OSError: [Errno 63] File name too long: '.../454545454545...'
```

Reachable over HTTP through the default response cache:

```python
import tempfile
from pathlib import Path

from litestar import get
from litestar.stores.file import FileStore
from litestar.testing import create_test_client


@get("/search", cache=True)
async def handler(q: str) -> str:
    return "ok"


store = FileStore(Path(tempfile.mkdtemp()))

with create_test_client(
    [handler], stores={"response_cache": store}, raise_server_exceptions=False
) as client:
    print("status:", client.get("/search", params={"q": "a b " * 100}).status_code)
```

```
status: 500
```

## Why This Is A Bug

Two documented contracts are broken:

1. `Store.get` is documented to return "The value associated with ``key`` if it exists and is not
   expired, else ``None``". `_load_from_path` catches only `FileNotFoundError`, so an over-long
   filename raises `OSError` (`ENAMETOOLONG`) instead of returning `None`. Since `FileStore` backs
   the response cache, this surfaces as an unhandled 500 on a request whose URL is merely long —
   no malformed input required.
2. `Store.set` is documented to store the value and return `None`. `_write_sync` wraps the whole
   write in `except OSError: pass`, so the failure is silent: `set()` reports success, `get()`
   later reports nothing was stored. Any `OSError` — disk full, permissions, read-only mount — is
   swallowed the same way.

The threshold is low because of the encoding's expansion factor: each non-alphanumeric character
costs 2–3 characters, so a 209-character cache key already overflows the 255-byte limit. URLs of
that length with query strings are routine.

## Fix

Bound the filename length by hashing the key — this also fixes the non-injectivity of the current
encoding (see the companion report on key collisions) and keeps the name ASCII. Nothing recovers a
key from a filename: `_path_from_key` is the only caller, and `delete_expired` iterates files and
reads their contents.

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

Independently, the two error-handling asymmetries are worth correcting regardless of the encoding:

```diff
@@ class FileStore(NamespacedStore):
     @staticmethod
     async def _load_from_path(path: Path) -> StorageObject | None:
         try:
             data = await path.read_bytes()
             return StorageObject.from_bytes(data)
-        except FileNotFoundError:
+        except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
             return None
```

and `_write_sync` should let `OSError` propagate (or at minimum log it) rather than silently
reporting success for a write that never happened.

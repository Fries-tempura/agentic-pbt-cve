# Bug Report: litestar.stores.file FileStore maps distinct keys to the same file

**Target**: `litestar.stores.file.FileStore` / `_safe_file_name`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`FileStore` turns keys into file names with `_safe_file_name`, which replaces each non-alphanumeric character with its decimal code point. Digits are left as they are, so the mapping is not injective. For example, `":"` and `"58"` both map to the file `58`, and `"-"` and `"45"` both map to `45`. NFKD normalization causes more collisions (for example, `"ﬁ"` and `"fi"`). As a result, one key can read, overwrite or delete another key's value.

## Property-Based Test

```python
import asyncio, tempfile
from pathlib import Path
from hypothesis import given, settings, assume, strategies as st
from litestar.stores.file import FileStore, _safe_file_name

@settings(max_examples=200, deadline=None)
@given(st.text(alphabet=st.characters(codec="ascii", categories=["P","S","Zs"]), min_size=1, max_size=10))
def test_encoded_key_does_not_alias(k1):
    k2 = _safe_file_name(k1)
    assume(k1 != k2)
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(k1, b"secret")
            return await s.get(k2)
    assert asyncio.run(go()) is None
```

**Failing input**: `k1=':'` (so `k2='58'`)

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        s = FileStore(Path(d))
        await s.set("-", b"dash")
        assert await s.get("45") == b"dash"
        await s.set("45", b"forty-five")
        assert await s.get("-") == b"forty-five"
        await s.set("ﬁ", b"ligature")
        assert await s.get("fi") == b"ligature"

asyncio.run(main())
```

## Why This Is A Bug

A key/value store has to keep distinct keys separate. `get` is documented to return "the value associated with `key`", but here it can return a value that was stored under a different key. Litestar uses stores for server-side sessions, response caching and rate limiting. Many of those keys come from the client, such as request paths, session IDs or client IPs like `127.0.0.1` vs `127461048461048461`. An attacker can choose a key that aliases another entry. They can then read it (cache or session leak), overwrite it (cache poisoning or session fixation) or delete it. The in-memory and Redis stores do not have this behavior, so the backends disagree.

Related issue found by the same tests: long keys produce file names longer than the OS limit (about 255 bytes). `set` hits an `OSError` inside `_write_sync`, swallows it and silently drops the value. `get` then crashes with an unhandled `OSError: [Errno 63] File name too long`, because `_load_from_path` only catches `FileNotFoundError`. Failing input: a key of `"k" * 256`.

## Fix

Use an injective, fixed-length encoding of the key, such as a cryptographic hash. This prevents collisions and keeps file names short enough for the OS limit:

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

# Bug Report: litestar.stores.file FileStore.set silently drops long keys, then get raises OSError

**Target**: `litestar.stores.file.FileStore.set` / `FileStore.get`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-05

## Summary

The key is converted to a filename without a length limit, and every non-alphanumeric character expands to 2–7 digits. A key whose filename passes the filesystem limit (usually 255 bytes) fails in `set`: `_write_sync` catches the `OSError` and discards it, so the value is never stored. A later `get` on the same key raises an unhandled `OSError: [Errno 63] File name too long`. It doesn't return `None`.

## Property-Based Test

```python
import asyncio, tempfile
from pathlib import Path
from hypothesis import given, settings, strategies as st
from litestar.stores.file import FileStore

@settings(max_examples=50)
@given(st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=128, max_size=400))
def test_set_then_get_long_key(key):
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(key, b"v")
            return await s.get(key)
    assert asyncio.run(go()) == b"v"
```

**Failing input**: a 128+ character ASCII key containing punctuation, e.g. `'0'*111 + ':'*62 + '{'*7`. `'x'*300` fails as well.

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.set("x" * 300, b"v")
        await store.get("x" * 300)  # OSError: File name too long

asyncio.run(main())
```

## Why This Is A Bug

`set` reports success but stores nothing. `get` is documented to return the value or `None`, but it crashes instead. Response-cache keys contain the request path and query string, so a client can send a long URL and cause a 500 error when the cache is backed by `FileStore`. An 86-character key made only of `"~"` already produces a filename longer than 255 bytes, because each `"~"` becomes `"126"`. On macOS, the same silent drop happens for code points that APFS rejects (for example `'\U00013460'`, which fails with `EILSEQ`).

## Fix

Hash the key to a fixed-length filename, and don't silently ignore write errors:

```diff
 def _safe_file_name(name: str) -> str:
-    name = unicodedata.normalize("NFKD", name)
-    return "".join(c if c.isalnum() else str(ord(c)) for c in name)
+    return hashlib.sha256(name.encode("utf-8")).hexdigest()
```

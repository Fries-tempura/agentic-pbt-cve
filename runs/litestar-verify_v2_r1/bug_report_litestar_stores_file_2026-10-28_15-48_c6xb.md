# Bug Report: litestar.stores.file.FileStore silently drops long keys on set, then get raises OSError

**Target**: `litestar.stores.file.FileStore.set` / `get`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

The key is mapped to a file name that grows with the key, and each non-alphanumeric character becomes 2–7 digits. When the name passes the file system's limit (255 bytes on most systems), `_write_sync` swallows the `OSError`, so `set` returns as if it succeeded. A later `get` on the same key raises `OSError: [Errno 63/36] File name too long`. Fewer than 128 characters is enough for keys made of `/`, `?`, `&`, `=` and similar characters, such as URL-derived cache keys.

## Property-Based Test

```python
@settings(max_examples=200, deadline=None)
@given(k=st.text(min_size=1, max_size=300), v=st.binary(max_size=8))
def test_set_then_get(k, v):
    """CLAIM-4: set followed by get returns the value for any str key."""
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d) / "s")
        async def go():
            await store.set(k, v)
            return await store.get(k)
        assert run(go()) == v
```

**Failing input**: `k="x" * 300` (also `k="/" * 128`)

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    store = FileStore(Path(tempfile.mkdtemp()))
    await store.set("/" * 128, b"v")
    await store.get("/" * 128)

asyncio.run(main())
```

## Why This Is A Bug

`key` is typed as plain `str`, and no length limit is documented. `set` returns normally without storing anything, then `get` raises an undocumented `OSError` instead of returning the value or `None`. The bare `except OSError: pass` in `_write_sync` also hides any other write failure, such as a full disk or a permission error.

## Fix

Use a fixed-length file name (for example the SHA-256 hex digest of the key; see the key-collision report). Remove the blanket `except OSError: pass` so write failures reach the caller.

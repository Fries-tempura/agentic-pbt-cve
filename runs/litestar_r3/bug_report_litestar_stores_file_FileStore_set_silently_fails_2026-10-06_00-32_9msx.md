# Bug Report: litestar.stores.file FileStore.set silently drops values when the write fails

**Target**: `litestar.stores.file.FileStore.set` / `_write_sync`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`_write_sync` wraps the whole write in `except OSError: pass`. If the filesystem rejects the filename derived from the key, `set()` returns normally but stores nothing. Two examples: a non-ASCII alphanumeric character that `_safe_file_name` keeps unchanged, but that macOS APFS rejects with `EILSEQ`, such as `"\U00013460"`; and a long key that exceeds the filesystem's maximum filename length (`ENAMETOOLONG`). A later `get()` then returns `None` for the illegal-character case. For the long-key case, `get()` raises `OSError: [Errno 63] File name too long`, even though `set()` reported success.

## Property-Based Test

```python
import tempfile
from pathlib import Path

import anyio
from hypothesis import given, settings, strategies as st

from litestar.stores.file import FileStore


@settings(max_examples=200, deadline=None)
@given(st.text(min_size=1), st.binary())
def test_set_get_roundtrip(k, v):
    async def main():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            await store.set(k, v)
            return await store.get(k)

    assert anyio.run(main) == v
```

**Failing input**: `k='\U00013460'` (`'𓑠'`), `v=b''` (any value fails) on macOS

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.set("\U00013460", b"value")
        print(await store.get("\U00013460"))  # None
        await store.set("a" * 300, b"value")  # returns normally
        await store.get("a" * 300)            # OSError: File name too long

asyncio.run(main())
```

## Why This Is A Bug

`set()` is documented to associate a value with a key, and it reports success. However, the value is silently lost, so callers such as session middleware or caches cannot detect the failure. The same input works with `MemoryStore` and `RedisStore`.

## Fix

Use a fixed-length ASCII filename, such as a SHA-256 hex digest of the key, so that valid keys cannot be rejected by the filesystem. Also stop swallowing `OSError` in `_write_sync`: clean up the temporary file, then re-raise the error.

```diff
-        except OSError:
-            pass
```

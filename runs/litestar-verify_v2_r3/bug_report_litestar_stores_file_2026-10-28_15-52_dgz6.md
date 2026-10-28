# Bug Report: litestar.stores.file.FileStore set() silently drops values and get() then crashes

**Target**: `litestar.stores.file.FileStore.set` / `.get`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

`_write_sync` catches every `OSError` and discards it, so `set()` returns normally even when nothing was written. With a long key (about 255 bytes or more after encoding), the write fails with ENAMETOOLONG. A later `get()` or `exists()` then raises an undocumented `OSError`, because `_load_from_path` only handles `FileNotFoundError`. Keys the filesystem rejects for other reasons are also lost silently: on macOS/APFS, `set("𓑠", b"")` succeeds but `get` returns `None`.

## Property-Based Test

```python
@settings(max_examples=300, deadline=None)
@given(k=st.text(min_size=1, max_size=300), v=st.binary(max_size=20))
def test_set_get_roundtrip(k, v):
    """CLAIM-2/CLAIM-3: set then get returns the value; no crash."""
    async def body(store):
        await store.set(k, v)
        return await store.get(k)
    assert run(body) == v
```

**Failing input**: `k='𓑠', v=b''` (get returns None). Also `k='x'*300` (get raises OSError).

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main(d):
    s = FileStore(Path(d))
    await s.set("x" * 300, b"v")
    await s.get("x" * 300)

with tempfile.TemporaryDirectory() as d:
    asyncio.run(main(d))
```

```
OSError: [Errno 63] File name too long: '.../xxxx...'
```

## Why This Is A Bug

`set` is annotated to accept any `str` key and documents no failure mode, yet it silently loses data. `get` documents that it returns `None` for missing keys, but it raises instead. Since non-alphanumeric characters expand to several digits each, a key of about 50 punctuation characters, such as a URL used as a cache key, is already too long.

## Fix

Map keys to a fixed-length name (for example a SHA-256 hex digest, which also fixes the key collisions), and stop discarding `OSError` in `_write_sync`. Clean up the temporary file, then re-raise the error.

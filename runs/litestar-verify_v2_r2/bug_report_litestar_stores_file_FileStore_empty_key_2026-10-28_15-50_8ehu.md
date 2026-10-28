# Bug Report: litestar.stores.file FileStore silently drops and then crashes on the empty key

**Target**: `litestar.stores.file.FileStore.set` / `.get`
**Severity**: Low
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

For `key=""`, `_path_from_key` returns the store directory itself. `set("", v)` silently fails: the `OSError` from `os.replace` onto a directory is swallowed. `get("")` then raises `IsADirectoryError`, where the API documents a return of `None` or the value.

## Property-Based Test

```python
@settings(max_examples=200, deadline=None)
@given(k=st.text(max_size=300))
def test_round_trip_any_key(k):
    """CLAIM-4: set then get round-trips for any str key without raising."""
    async def go():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            await store.set(k, b"v")
            return await store.get(k)
    assert asyncio.run(go()) == b"v"
```

**Failing input**: `k=''`

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.set("", b"v")
        await store.get("")  # IsADirectoryError

asyncio.run(main())
```

## Why This Is A Bug

`key` is annotated `str`, and the empty string is accepted without any error. The write is lost silently, and the following `get` raises an undocumented exception instead of returning the value or `None`.

## Fix

Use an encoding for file names that never yields an empty name, for example the sha256 hexdigest proposed in the companion key-collision report. The alternative is to reject empty keys explicitly with `ValueError`.

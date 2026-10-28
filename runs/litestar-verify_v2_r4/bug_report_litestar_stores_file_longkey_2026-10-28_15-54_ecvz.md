# Bug Report: litestar.stores.file.FileStore.set silently drops values for long keys, then get raises OSError

**Target**: `litestar.stores.file.FileStore.set` / `get`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`_safe_file_name` expands every non-alphanumeric character into several digits, so the file name can exceed the filesystem's NAME_MAX (255 bytes). A key like `"k"*300`, or a ~300-character URL full of `/`, `?` and `=`, is enough. `_write_sync` catches the resulting `OSError` and ignores it, so `set` returns normally without storing anything. A later `get` on the same key then raises `OSError: File name too long`. `_load_from_path` only catches `FileNotFoundError`.

## Property-Based Test

```python
@settings(max_examples=300, deadline=None)
@given(k=st.text(min_size=1, max_size=300), v=st.binary(max_size=20))
def test_set_get_roundtrip(k, v):
    """CLAIM-3: a set that returns normally makes the value retrievable."""
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(k, v)
            return await s.get(k)
    assert asyncio.run(go()) == v
```

**Failing input**: `k="k"*300` (Hypothesis also found `k='𓑠'`: Python treats this Unicode 16 character as alphanumeric and keeps it verbatim, macOS rejects it in a file name, and the write is silently dropped)

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        s = FileStore(Path(d))
        key = "/api/items?" + "&".join(f"f{i}=x" for i in range(60))
        await s.set(key, b"value")
        print(await s.get(key))

asyncio.run(main())
```

## Why This Is A Bug

`set` documents no failure mode, yet it silently discards the write. `get` then raises an undocumented `OSError` where it should return the value (or at worst `None`). Response-cache keys built from long URLs hit this path.

## Fix

Use a fixed-length file name, such as the sha256 hex digest of the key (see the key-collision report). Also stop swallowing `OSError` in `_write_sync`: clean up the temp file, then re-raise.

# Bug Report: litestar.stores.file.FileStore distinct keys map to the same file

**Target**: `litestar.stores.file.FileStore` (`_safe_file_name`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`_safe_file_name` replaces every non-alphanumeric character with its decimal code point and applies NFKD normalization, so it is not injective. Distinct keys such as `"-"` and `"45"`, or `"ﬁ"` and `"fi"`, are stored in the same file, and writing one key silently overwrites the other.

## Property-Based Test

```python
@settings(max_examples=300, deadline=None)
@given(ks=st.lists(st.text(alphabet="a45-ﬁf ", min_size=1, max_size=3), unique=True, min_size=2, max_size=8))
def test_distinct_keys_isolated(ks):
    """CLAIM-1: distinct keys keep distinct values."""
    async def body(store):
        for i, k in enumerate(ks):
            await store.set(k, str(i))
        return [await store.get(k) for k in ks]
    got = run(body)
    assert got == [str(i).encode() for i in range(len(ks))], list(zip(ks, got))
```

**Failing input**: `ks=['-', '45']`

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main(d):
    s = FileStore(Path(d))
    await s.set("-", b"dash")
    await s.set("45", b"forty-five")
    assert await s.get("-") == b"dash", await s.get("-")

with tempfile.TemporaryDirectory() as d:
    asyncio.run(main(d))
```

## Why This Is A Bug

A key/value store must keep distinct keys apart. Here, different keys share one file. If the keys come from users (session IDs, cache keys built from request paths or query strings), one client can read or overwrite another client's entry, for example `"user-1"` collides with `"user451"`. NFKD normalization causes more collisions (`"ﬁ"` vs `"fi"`, `"²"` vs `"2"`).

## Fix

Use an injective encoding, for example a fixed-width hex digest of the key:

```diff
-def _safe_file_name(name: str) -> str:
-    name = unicodedata.normalize("NFKD", name)
-    return "".join(c if c.isalnum() else str(ord(c)) for c in name)
+def _safe_file_name(name: str) -> str:
+    return hashlib.sha256(name.encode("utf-8")).hexdigest()
```

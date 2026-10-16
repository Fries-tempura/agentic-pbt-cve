# Bug Report: litestar.stores.file FileStore maps distinct keys to the same file

**Target**: `litestar.stores.file.FileStore` (`_safe_file_name`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-16

## Summary

`_safe_file_name` replaces every non-alphanumeric character with its decimal code point and applies NFKD normalisation. As a result the key-to-filename mapping is not injective, and distinct keys share one file. For example, `"a."` and `"a46"` both become `a46`, and `"ﬁ"` and `"fi"` both become `fi`. A `set`, `get` or `delete` on one key reads or overwrites the value of the other key.

## Property-Based Test

```python
@settings(max_examples=1000, deadline=None)
@given(st.text(min_size=1), st.text(min_size=1), st.binary(), st.binary())
def test_distinct_keys_independent(k1, k2, v1, v2):
    """CLAIM-2: distinct keys hold independent values."""
    assume(k1 != k2 and v1 != v2)
    async def go(s):
        await s.set(k1, v1)
        await s.set(k2, v2)
        return await s.get(k1), await s.get(k2)
    assert run(go) == (v1, v2)
```

**Failing input**: Hypothesis reported `k1='0', k2='{¡{{{¨{0««¯´´0´´00¼/0ÅÍ…☃\uf8ff', v1=b'', v2=b'\x00'` and `get(k2)` returned `None`. That shrunk case shows a related failure. k2 sanitises to a filename over 255 bytes, `_write_sync` swallows the `OSError`, and the value is silently dropped. The collision itself was found by inspecting the encoding and was confirmed with `k1="a.", k2="a46"` (see below). It was not produced by Hypothesis.

## Reproducing the Bug

```python
import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.set("a.", b"first")
        await store.set("a46", b"second")
        assert await store.get("a.") == b"first"

asyncio.run(main())
```

Output: `get("a.")` returns `b'second'`. Also, after `set("ﬁ", ...)` and `set("fi", ...)`, the value for `"ﬁ"` is lost, and `delete("a46")` deletes the value for `"a."`.

## Why This Is A Bug

`Store.get` is documented to return "the value associated with `key`". With FileStore, writing one key silently replaces another key's value. This has security impact. The default response-cache key is `method + path + query`. In that key, `GET/a/b` and `GET/a47b` map to the same file (`GET47a47b`). A request to one URL can therefore poison the cached response served for a different URL. The same applies to rate-limit or other keys stored in a FileStore.

## Fix

Use an injective encoding for filenames, for example a hash of the key's UTF-8 bytes. A hash also stays within filename-length limits, unlike the current encoding. With the current encoding a key of about 100 characters produces a name over 255 bytes. `set` swallows the resulting `OSError` and `get`/`delete` raise it.

```diff
-import unicodedata
+import hashlib
@@
 def _safe_file_name(name: str) -> str:
-    name = unicodedata.normalize("NFKD", name)
-    return "".join(c if c.isalnum() else str(ord(c)) for c in name)
+    return hashlib.sha256(name.encode("utf-8")).hexdigest()
```

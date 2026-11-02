# Bug Report: setuptools.package_index.PackageIndex.download writes outside tmpdir (path traversal)

**Target**: `setuptools.package_index.PackageIndex.download` / `PackageIndex._resolve_download_filename`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`download()` promises to save a URL "to a subpath of `tmpdir`". But `_resolve_download_filename` URL-unquotes the last path segment. When that segment contains `%2F`, the unquoted name is an absolute path, and `os.path.join(tmpdir, name)` throws `tmpdir` away. Anyone who controls a download URL, such as a link on a package index page, can then write a file anywhere the user can write.

## Property-Based Test

```python
import os, urllib.parse
from hypothesis import given, settings, strategies as st
from setuptools.package_index import PackageIndex

TMP = os.path.realpath("/tmp/pi_dl_root")
segment = st.text(alphabet="abc.-_/\\", min_size=1, max_size=12)

@settings(max_examples=1000)
@given(st.lists(segment, min_size=1, max_size=4), st.booleans())
def test_download_stays_in_tmpdir(segs, quote_all):
    """CLAIM-1: the resolved download filename lies inside tmpdir."""
    last = urllib.parse.quote(segs[-1], safe="" if quote_all else "/")
    url = "https://example.com/" + "/".join(["d"] + segs[:-1]).replace("//", "/") + "/" + last
    p = os.path.realpath(PackageIndex._resolve_download_filename(url, TMP))
    assert os.path.commonpath([p, TMP]) == TMP, (url, p)
```

**Failing input**: `segs=['/'], quote_all=True` → URL `https://example.com/d/%2F` resolves to `/`

## Reproducing the Bug

```python
import email.message, io, os
from setuptools.package_index import PackageIndex

class Resp(io.BytesIO):
    def info(self):
        m = email.message.Message(); m["content-type"] = "application/octet-stream"; return m

os.makedirs("/tmp/pi_e2e/tmpdir", exist_ok=True)
pi = PackageIndex()
pi.open_url = lambda url, warning=None: Resp(b"pwned")
out = pi.download("https://example.com/pkg/%2Ftmp%2Fpi_e2e%2Fescaped.tar.gz", "/tmp/pi_e2e/tmpdir")
print(out)                                  # /tmp/pi_e2e/escaped.tar.gz
print(os.listdir("/tmp/pi_e2e/tmpdir"))     # []
```

## Why This Is A Bug

The `download` docstring says: "If `spec` is a URL, it is downloaded to a subpath of `tmpdir`". The `..`-stripping loop in `_resolve_download_filename` shows that the code is meant to keep the name inside `tmpdir`. An absolute name gets past that check completely. Download URLs come from remote index pages and `find_links`, so an attacker controls them. This allows arbitrary file writes, which could, for example, overwrite `~/.bashrc` or a module on `sys.path`. This is CVE-2025-47273.

## Fix

```diff
@@ def _resolve_download_filename(url, tmpdir):
         if name.endswith('.egg.zip'):
             name = name[:-4]  # strip the extra .zip before download

-        return os.path.join(tmpdir, name)
+        filename = os.path.join(tmpdir, name)
+
+        # ensure path resolves within the tmpdir
+        if not filename.startswith(str(tmpdir)):
+            raise ValueError(f"Invalid filename {filename}")
+
+        return filename
```

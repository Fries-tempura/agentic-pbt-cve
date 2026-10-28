# Bug Report: setuptools.package_index Download filename escapes tmpdir (path traversal)

**Target**: `setuptools.package_index.PackageIndex._resolve_download_filename` / `_download_url`
**Severity**: High
**Bug Type**: Logic (security)
**Date**: 2026-10-28

## Summary

`_resolve_download_filename` URL-decodes the last path segment of the URL and passes it to `os.path.join(tmpdir, name)`. If the segment contains an encoded slash (`%2F`) so that it decodes to an absolute path, `os.path.join` throws away `tmpdir`. `PackageIndex.download()` / `_download_url` then writes the downloaded file to whatever path the attacker picked. The existing `..` stripping doesn't stop this. This is the same issue as CVE-2025-47273.

## Property-Based Test

```python
import os, urllib.parse, tempfile
from hypothesis import given, settings, strategies as st
from setuptools.package_index import PackageIndex

seg = st.text(st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"), min_size=1)

@settings(max_examples=2000)
@given(seg)
def test_download_filename_stays_in_tmpdir(name):
    tmpdir = tempfile.gettempdir() + "/pkgroot"
    url = "https://example.com/packages/" + urllib.parse.quote(name, safe="")
    result = PackageIndex._resolve_download_filename(url, tmpdir)
    root = os.path.realpath(tmpdir)
    assert os.path.commonpath([root, os.path.realpath(result)]) == root, (url, result)
```

**Failing input**: `name='/'` (URL `https://example.com/packages/%2F` resolves to `/`)

## Reproducing the Bug

```python
from setuptools.package_index import PackageIndex
print(PackageIndex._resolve_download_filename(
    "https://example.com/%2Fhome%2Fuser%2F.bashrc", "/tmp/pkgroot"))
# /home/user/.bashrc
```

## Why This Is A Bug

The function's job, as its doctest shows, is to pick a download target inside `tmpdir`. The `..` replacement loop shows the authors meant to stop traversal. URLs come from untrusted package index pages (`find_links`, `process_index`, `download(spec, tmpdir)`). A malicious index can serve a link such as `/%2Fhome%2Fuser%2F.ssh%2Fauthorized_keys` and get arbitrary files overwritten with attacker-controlled content, which can lead to code execution.

## Fix

```diff
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

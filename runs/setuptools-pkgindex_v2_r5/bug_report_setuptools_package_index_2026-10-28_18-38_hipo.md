# Bug Report: setuptools.package_index PackageIndex.download writes outside tmpdir (path traversal)

**Target**: `setuptools.package_index.PackageIndex._resolve_download_filename` / `PackageIndex.download`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

If the last path segment of a download URL contains a percent-encoded `/` (`%2F`), it is unquoted into an absolute path. `os.path.join(tmpdir, name)` then throws away `tmpdir`, so the download is written to any path the URL names.

## Property-Based Test

```python
seg_atoms = st.sampled_from(
    ["a", "b", "pkg", "1.0", ".", "..", "%2F", "%2f", "%5C", "\\", "%2E", "-", "_", ".tar.gz", "/"]
)
segment = st.lists(seg_atoms, min_size=1, max_size=8).map("".join)

@settings(max_examples=1000)
@given(segment)
def test_download_filename_inside_tmpdir(seg):
    """CLAIM-1: the download filename is strictly inside tmpdir."""
    url = "https://files.example.org/packages/" + seg
    result = PackageIndex._resolve_download_filename(url, TMPDIR)
    norm = os.path.normpath(result)
    assert os.path.commonpath([norm, TMPDIR]) == TMPDIR, (url, result)
```

**Failing input**: `seg='%2F'` → the result is `'/'`

## Reproducing the Bug

```python
from setuptools.package_index import PackageIndex

print(PackageIndex._resolve_download_filename(
    'https://example.org/pkgs/%2Ftmp%2Fevil%2Fsetup.tar.gz', '/tmp/safe_dir'))

pi = PackageIndex()
pi._download_to = lambda url, fn: (print('writing to', fn), {})[1]
pi.download('https://example.org/pkgs/%2Ftmp%2Fevil%2Fsetup.tar.gz', '/tmp/safe_dir')
```

Output: `/tmp/evil/setup.tar.gz` (twice). The file is placed outside `/tmp/safe_dir`.

## Why This Is A Bug

The docstring of `PackageIndex.download` says: "If `spec` is a URL, it is downloaded to a subpath of `tmpdir`". The `..` stripping loop in `_resolve_download_filename` shows the author meant to keep the name inside tmpdir. That loop does not catch an absolute path. A malicious index page or link can make setuptools overwrite any file the user can write (for example `~/.bashrc`). This is the behaviour reported as CVE-2025-47273.

## Fix

```diff
--- a/setuptools/package_index.py
+++ b/setuptools/package_index.py
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

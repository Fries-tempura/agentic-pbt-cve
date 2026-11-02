# Bug Report: setuptools.package_index PackageIndex.download writes outside tmpdir (path traversal)

**Target**: `setuptools.package_index.PackageIndex.download` / `PackageIndex._resolve_download_filename`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

If the last path segment of a URL percent-decodes to an absolute path (e.g. `%2Ftmp%2Fevil.tar.gz`), `_resolve_download_filename` returns that absolute path. `os.path.join` then throws `tmpdir` away, so `download()` writes the file wherever the URL says. The `..` scrubbing does not stop this.

## Property-Based Test

```python
seg_chars = string.ascii_letters + string.digits + "._-/\\%:"
TMP = os.path.realpath(tempfile.mkdtemp())

@settings(max_examples=1000)
@given(seg=st.text(alphabet=seg_chars, min_size=1, max_size=20))
def test_download_stays_in_tmpdir(seg):
    """CLAIM-1: URL downloads resolve to a path strictly inside tmpdir."""
    url = "https://example.com/pkgs/" + urllib.parse.quote(seg, safe="")
    path = os.path.realpath(PackageIndex._resolve_download_filename(url, TMP))
    assert os.path.commonpath([path, TMP]) == TMP and path != TMP, (url, path)
```

**Failing input**: `seg='/'` (URL `https://example.com/pkgs/%2F`, which resolves to `/`)

## Reproducing the Bug

```python
import tempfile
from setuptools.package_index import PackageIndex

tmpdir = tempfile.mkdtemp()
print(PackageIndex._resolve_download_filename("https://example.com/%2Ftmp%2Fevil.tar.gz", tmpdir))
```

Output: `/tmp/evil.tar.gz`. It should be a path under `tmpdir`.

## Why This Is A Bug

The `download` docstring says: "If `spec` is a URL, it is downloaded to a subpath of `tmpdir`". `_download_url` writes to the path that `_resolve_download_filename` returns. The `..` stripping shows that the filename is meant to stay inside `tmpdir`. An attacker who controls a URL that `PackageIndex` downloads (for example, a link on an index page) can write a file anywhere the user can write. This is CVE-2025-47273, fixed upstream in setuptools 78.1.1.

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

# Bug Report: setuptools.package_index `_resolve_download_filename` path traversal via encoded `/`

**Target**: `setuptools.package_index.PackageIndex._resolve_download_filename` (used by `PackageIndex.download` / `_download_url`)
**Severity**: High
**Bug Type**: Logic (security: arbitrary file write)
**Date**: 2026-10-28

## Summary

The download filename comes from the URL-decoded last path segment. A percent-encoded slash (`%2F`) survives `path.split('/')` and then becomes `/` after unquoting, so the name can be an absolute path. `os.path.join(tmpdir, name)` then throws `tmpdir` away, and the download is written to an arbitrary location the attacker picks. The `..` sanitization does not help, because no `..` is needed.

## Property-Based Test

```python
import os, urllib.parse
from hypothesis import given, settings, strategies as st
from setuptools.package_index import PackageIndex

seg = st.text(alphabet=st.characters(codec="ascii", exclude_characters="\x00"), min_size=1)

@settings(max_examples=1000)
@given(seg)
def test_download_filename_stays_in_tmpdir(name):
    tmpdir = "/tmp/pkgidx_root"
    url = "https://example.com/packages/" + urllib.parse.quote(name, safe="")
    result = PackageIndex._resolve_download_filename(url, tmpdir)
    real = os.path.normpath(result)
    assert os.path.commonpath([real, tmpdir]) == tmpdir, (url, result)
```

**Failing input**: `name='/'` (URL `https://example.com/packages/%2F` → result `/`)

## Reproducing the Bug

```python
from setuptools.package_index import PackageIndex

print(PackageIndex._resolve_download_filename("https://example.com/%2Fhome%2Fuser%2F.ssh%2Fauthorized_keys", "/tmp/build"))
print(PackageIndex._resolve_download_filename("https://example.com/%2Fetc%2Fpasswd", "/tmp/build"))
```

Output:
```
/home/user/.ssh/authorized_keys
/etc/passwd
```

## Why This Is A Bug

The function's doctest shows that it returns a path relative to `tmpdir`. The `..` stripping loop shows the authors meant to keep downloads inside `tmpdir`. `PackageIndex.download()` passes this filename straight to `_download_to`, which opens it for writing. A malicious index page or `--find-links` URL can therefore overwrite any file the user can write to (this is CVE-2025-47273). On Windows, a drive-letter name such as `C:%5C...` works the same way.

## Fix

```diff
     @staticmethod
     def _resolve_download_filename(url, tmpdir):
         name, _fragment = egg_info_for_url(url)
         if name:
             while '..' in name:
                 name = name.replace('..', '.').replace('\\', '_')
         else:
             name = "__downloaded__"  # default if URL has no path contents

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

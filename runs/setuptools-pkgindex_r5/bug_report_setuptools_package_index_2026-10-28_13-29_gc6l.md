# Bug Report: setuptools.package_index Download Path Escapes tmpdir (Path Traversal)

**Target**: `setuptools.package_index.PackageIndex._resolve_download_filename` / `PackageIndex.download`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`PackageIndex.download()` is documented to save a URL "to a subpath of `tmpdir`". But the filename comes from the URL-decoded last path segment. If that segment contains `%2F`, it decodes to an absolute path, and `os.path.join(tmpdir, name)` throws away `tmpdir`. The downloaded content is then written to any path the URL's author picks.

## Property-Based Test

```python
import os, urllib.parse
from hypothesis import given, settings, strategies as st
from setuptools.package_index import PackageIndex

seg = st.text(alphabet=st.characters(codec="utf-8", exclude_categories=["Cs"], exclude_characters="\x00"), min_size=1)

@settings(max_examples=1000)
@given(seg)
def test_download_filename_is_subpath_of_tmpdir(name):
    tmpdir = "/tmp/pkgidx_root"
    url = "https://example.com/packages/" + urllib.parse.quote(name, safe="")
    result = PackageIndex._resolve_download_filename(url, tmpdir)
    real = os.path.normpath(result)
    assert os.path.commonpath([real, tmpdir]) == tmpdir, (url, result)
```

**Failing input**: `name='/'`, which gives the URL `https://example.com/packages/%2F` and resolves to `'/'`

## Reproducing the Bug

```python
import http.server, os, tempfile, threading
from setuptools.package_index import PackageIndex

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "application/octet-stream"); self.end_headers()
        self.wfile.write(b"pwned")
    def log_message(self, *a): pass

srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

tmpdir = tempfile.mkdtemp()
target = os.path.join(tempfile.mkdtemp(), "outside.txt")
url = f"http://127.0.0.1:{srv.server_port}/pkgs/" + target.replace("/", "%2F")

result = PackageIndex().download(url, tmpdir)
print(result, os.path.exists(target), result.startswith(tmpdir))
# -> <target path> True False
```

Simpler, without a network call:

```python
from setuptools.package_index import PackageIndex
print(PackageIndex._resolve_download_filename("https://example.com/pkgs/%2Fetc%2Fpasswd", "/tmp/dl"))
# -> /etc/passwd
```

## Why This Is A Bug

The `download()` docstring says: "If `spec` is a URL, it is downloaded to a subpath of `tmpdir`". `_resolve_download_filename` tries to clean the name: it collapses `..` and replaces `\`. It never checks for an absolute path, though, and that path comes from `urllib.parse.unquote`. URLs come from package index pages and `find_links`, which may be controlled by an attacker. So a malicious index can overwrite any file the user can write, such as `~/.bashrc` or files in site-packages. This is an arbitrary file write that can lead to code execution (CVE-2025-47273).

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

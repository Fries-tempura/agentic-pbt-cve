# Bug Report: wlc.main.Download Path traversal via server-supplied slugs

**Target**: `wlc.main.Download.download_component`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`wlc download --output DIR` builds the file name from `component.project.slug` and `component.slug`, which come from the server, and doesn't sanitize them. A slug containing `../` or starting with `/` makes wlc write the ZIP outside `DIR`, or to any absolute path.

## Property-Based Test

```python
seg = st.text(alphabet=st.sampled_from(list("abc-_./")), min_size=1, max_size=12)

@given(seg, seg)
def test_download_stays_in_output_dir(pslug, cslug):
    with tempfile.TemporaryDirectory() as root:
        out = Path(root) / "a" / "b" / "out"
        cmd = Download.__new__(Download)
        cmd.args = SimpleNamespace(output=str(out), convert=None, no_glossary=False)
        comp = SimpleNamespace(project=SimpleNamespace(slug=pslug), slug=cslug,
                               download=lambda convert: b"zip")
        written = []
        real_open = open
        def fake_open(p, mode="r", *a, **k):
            written.append(os.path.abspath(p))
            return real_open(os.devnull, mode)
        with mock.patch("builtins.open", fake_open):
            cmd.download_component(comp)
        for w in written:
            assert w.startswith(os.path.abspath(out) + os.sep)
```

**Failing input**: `pslug='/', cslug='_'`. The output is written to `/-_.zip`.

## Reproducing the Bug

```python
import tempfile
from pathlib import Path
from types import SimpleNamespace
from wlc.main import Download

root = Path(tempfile.mkdtemp())
out = root / "out"
cmd = Download.__new__(Download)
cmd.args = SimpleNamespace(output=str(out), convert=None, no_glossary=False)
comp = SimpleNamespace(project=SimpleNamespace(slug="../escaped"), slug="x", download=lambda c: b"PK")
cmd.download_component(comp)
print(sorted(str(p.relative_to(root)) for p in root.rglob("*")))
# ['escaped-x.zip', 'out']  -> file written outside --output
```

## Why This Is A Bug

`--output` is documented as the "Directory where to store output". Slugs come from the remote API (`list_components()` / `project.list()`). A malicious or compromised Weblate server, or a man-in-the-middle, can set them so that wlc creates or overwrites any file the user can write. That is a path traversal / arbitrary file write.

## Fix

```diff
--- a/wlc/main.py
+++ b/wlc/main.py
@@ def download_component(self, component) -> None:
         directory = Path(self.args.output)
-        file_path = directory.joinpath(f"{component.project.slug}-{component.slug}.zip")
+        file_name = f"{component.project.slug}-{component.slug}.zip"
+        file_path = directory.joinpath(file_name)
+        if (
+            Path(file_name).name != file_name
+            or not file_path.resolve().is_relative_to(directory.resolve())
+        ):
+            raise CommandError(f"Refusing to write outside output directory: {file_name}")
```

# Bug Report: wlc.main.Download.download_component Path traversal via server-supplied slugs

**Target**: `wlc.main.Download.download_component`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`wlc download -o DIR` writes each component archive to `DIR/{project.slug}-{component.slug}.zip`. The slugs come straight from the server's API response and are never sanitized. A slug that contains `/` or `../` therefore makes wlc write the file outside `DIR`, or to an absolute path such as `/-x.zip`. Any file the user can write may be created or overwritten this way.

## Property-Based Test

```python
slug_chars = string.ascii_letters + string.digits + "-_./"
slugs = st.text(alphabet=slug_chars, min_size=1, max_size=20)


class FakeComponent:
    def __init__(self, project_slug, slug):
        self.project = SimpleNamespace(slug=project_slug)
        self.slug = slug

    def download(self, convert=None):
        return b"PK"


@settings(max_examples=500, deadline=None)
@given(slugs, slugs)
def test_download_component_stays_in_output_dir(project_slug, slug):
    with tempfile.TemporaryDirectory() as base:
        out = Path(base).resolve() / "a" / "b" / "out"
        cmd = Download.__new__(Download)
        cmd.args = SimpleNamespace(convert=None, output=str(out))
        written = []
        real_open = open

        def fake_open(path, mode="r", *a, **k):
            written.append(Path(path))
            return real_open(os.devnull, mode)

        with mock.patch("builtins.open", fake_open):
            try:
                cmd.download_component(FakeComponent(project_slug, slug))
            except OSError:
                return
        for p in written:
            resolved = Path(os.path.normpath(p))
            assert out in resolved.parents, (p, resolved)
```

**Failing input**: `project_slug='/', slug='0'`. The file is written to `/-0.zip`.

## Reproducing the Bug

```python
import tempfile
from pathlib import Path
from types import SimpleNamespace
from wlc.main import Download

base = Path(tempfile.mkdtemp()).resolve()
out = base / "out"
component = SimpleNamespace(
    project=SimpleNamespace(slug="../escaped"), slug="x", download=lambda convert=None: b"PK"
)
cmd = Download.__new__(Download)
cmd.args = SimpleNamespace(convert=None, output=str(out))
cmd.download_component(component)
print(sorted(str(p.relative_to(base)) for p in base.rglob("*")))
# ['escaped-x.zip', 'out']  -> file landed outside the output directory
```

In real use, `component` comes from `Weblate.list_components()` / `Project.list()`, which build objects from the server's JSON. A malicious or compromised Weblate server, or a MITM on a plain-HTTP connection, controls `slug` and `project.slug`.

## Why This Is A Bug

The help text for `-o/--output` says it is the "Directory where to store output". The user expects every downloaded file to end up inside that directory. Because the slugs are used without validation, the server decides where on the client's filesystem the files go. For example, it can overwrite `~/.bashrc`-adjacent paths, or anything else the user can write.

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
+            or directory.resolve() not in file_path.resolve().parents
+        ):
+            raise CommandError(f"Refusing to write outside output directory: {file_name}")
 
         if not directory.exists():
             directory.mkdir(exist_ok=True, parents=True)
```

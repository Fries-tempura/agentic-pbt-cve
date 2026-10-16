# Bug Report: poetry.installation.wheel_installer Path traversal lets wheel members escape the install scheme

**Target**: `poetry.installation.wheel_installer.WheelDestination.write_to_fs` / `WheelInstaller.install`
**Severity**: High
**Bug Type**: Logic (Security)
**Date**: 2026-10-06

## Summary

`WheelDestination.write_to_fs` joins the wheel member path onto the scheme directory (`Path(scheme_dir) / path`) without normalising or validating it. A wheel that contains a member such as `../../escaped.txt` gets written outside the target environment. Writing over existing files only logs a warning, so the escaping file can also overwrite arbitrary files the user can write to.

## Property-Based Test

```python
segment = st.sampled_from(["..", "pkg", "a", "b", "evil.py"])
rel_paths = st.lists(segment, min_size=1, max_size=6).map("/".join).filter(
    lambda p: not p.endswith("..")
)

@settings(max_examples=300)
@given(rel_paths)
def test_write_to_fs_stays_in_scheme(path):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "x" / "y" / "z"
        sd = _scheme(root)
        dest = WheelDestination(sd, interpreter="python", script_kind="posix")
        rec = dest.write_to_fs("purelib", path, io.BytesIO(b"data"), False)
        written = (Path(sd["purelib"]) / rec.path).resolve()
        assert written.is_relative_to(Path(sd["purelib"]).resolve()), written
```

**Failing input**: `path='../pkg'` (end-to-end through `WheelInstaller.install`: wheel member `'../../pkg'`)

## Reproducing the Bug

```python
import tempfile, zipfile
from pathlib import Path
from poetry.installation.wheel_installer import WheelInstaller

tmp = Path(tempfile.mkdtemp())
venv = tmp / "venv"
class Env:
    scheme_dict = {k: str(venv / k) for k in ("purelib", "platlib", "scripts", "data", "include")}
    python = Path("/usr/bin/python3")

di = "demo-1.0.dist-info"
whl = tmp / "demo-1.0-py3-none-any.whl"
with zipfile.ZipFile(whl, "w") as z:
    z.writestr("../../escaped.txt", "pwned")
    z.writestr(f"{di}/METADATA", "Metadata-Version: 2.1\nName: demo\nVersion: 1.0\n")
    z.writestr(f"{di}/WHEEL", "Wheel-Version: 1.0\nGenerator: x\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
    z.writestr(f"{di}/RECORD", f"../../escaped.txt,,\n{di}/METADATA,,\n{di}/WHEEL,,\n{di}/RECORD,,\n")

WheelInstaller(Env()).install(whl)
print((tmp / "escaped.txt").exists())  # True: written outside venv/purelib
```

## Why This Is A Bug

A scheme-dictionary destination is supposed to install each wheel file *inside* the directory for its scheme (purelib, scripts, and so on). Wheel paths are defined relative to the wheel root. Neither `installer` 0.7.0 nor Poetry's overriding `write_to_fs` rejects `..` components or absolute paths, so a malicious or malformed wheel can write or overwrite files anywhere the user can write (shell rc files, other site-packages, and so on) when someone runs `poetry install`. Poetry's override makes this worse than the base class: it overwrites existing files with only a warning, where the base class raises `FileExistsError`.

## Fix

```diff
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

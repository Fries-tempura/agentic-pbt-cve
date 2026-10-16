# Bug Report: poetry.installation.wheel_installer Path traversal writes wheel files outside the install scheme

**Target**: `poetry.installation.wheel_installer.WheelDestination.write_to_fs` (via `WheelInstaller.install`)
**Severity**: High
**Bug Type**: Logic (security)
**Date**: 2026-10-05

## Summary

`WheelDestination.write_to_fs` joins the archive member path onto the scheme directory (`Path(self.scheme_dict[scheme]) / path`) without checking that the result stays inside that directory. If a wheel contains members like `../../../x` or an absolute path such as `/home/user/.bashrc`, `WheelInstaller.install` writes them anywhere on the filesystem. Poetry's override also stops raising on existing files, so it silently overwrites any file the user can write to.

## Property-Based Test

```python
segment = st.from_regex(r"[a-z][a-z0-9_]{0,7}", fullmatch=True)
member_path = st.lists(
    st.one_of(segment, st.just("..")), min_size=1, max_size=5
).map(lambda parts: "/".join([*parts, "payload.py"]))


@settings(max_examples=200, deadline=None)
@given(member_path)
def test_installed_files_stay_inside_scheme_dirs(extra_member: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp).resolve()
        venv = sandbox / "a" / "b" / "c" / "d" / "e" / "venv"
        whl = Path(tmp) / "demo-0.1.0-py3-none-any.whl"
        build_wheel(whl, extra_member)  # valid wheel incl. RECORD with hashes

        env = MockEnv(path=venv)
        WheelInstaller(env).install(whl)

        scheme_dirs = [
            Path(p).resolve()
            for k, p in env.scheme_dict.items()
            if k in ("purelib", "platlib", "scripts", "data")
        ]
        for f in sandbox.rglob("*"):
            if f.is_file() and f != whl.resolve():
                assert any(f.resolve().is_relative_to(d) for d in scheme_dirs)
```

**Failing input**: `extra_member='../payload.py'`

## Reproducing the Bug

```python
import tempfile
import zipfile

from pathlib import Path

from poetry.installation.wheel_installer import WheelInstaller
from poetry.utils.env import MockEnv

for member in ["../../../escaped.txt", str(Path("abs_escape.txt").resolve())]:
    tmp = Path(tempfile.mkdtemp()).resolve()
    whl = tmp / "demo-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(whl, "w") as zf:
        zf.writestr("demo-0.1.0.dist-info/METADATA", "Metadata-Version: 2.1\nName: demo\nVersion: 0.1.0\n")
        zf.writestr("demo-0.1.0.dist-info/WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        zf.writestr(member, "pwned\n")
        zf.writestr("demo-0.1.0.dist-info/RECORD", "")
    env = MockEnv(path=tmp / "project" / "venv")
    installer = WheelInstaller(env)
    installer.install(whl)
    target = Path(env.scheme_dict["purelib"]) / member
    print(member, "->", target.resolve(), target.exists())
```

Output:
```
../../../escaped.txt -> /private/var/folders/.../T/tmp3ne__yrb/escaped.txt True
/Users/.../runs/poetry/abs_escape.txt -> /Users/.../runs/poetry/abs_escape.txt True
```

The record validation failure only gets stored in `installer.invalid_wheels`, and the installation still runs. Even a wheel with a fully valid RECORD (as in the PBT) gets installed outside the scheme.

## Why This Is A Bug

The `write_to_fs` contract inherited from `installer` is to write `path` *within* the given scheme ("path within that scheme"). A wheel is untrusted input from a package index, so a malicious package can overwrite arbitrary user files (shell rc files, other packages, `site-packages/*.pth`) when installed with `poetry install`/`poetry add`. The override also removed the base class's `FileExistsError`, so existing files are silently overwritten. pip rejects such members ("has a file ... outside the target directory").

## Fix

```diff
--- a/src/poetry/installation/wheel_installer.py
+++ b/src/poetry/installation/wheel_installer.py
@@ -44,7 +44,13 @@ class WheelDestination(SchemeDictionaryDestination):
         from installer.utils import copyfileobj_with_hashing
         from installer.utils import make_file_executable
 
-        target_path = Path(self.scheme_dict[scheme]) / path
+        scheme_path = Path(self.scheme_dict[scheme]).resolve()
+        target_path = (scheme_path / path).resolve()
+        if not target_path.is_relative_to(scheme_path):
+            raise ValueError(
+                f"Attempting to write {path} outside of the target directory"
+            )
+
         if target_path.exists():
             # Contrary to the base library we don't raise an error here since it can
             # break pkgutil-style and pkg_resource-style namespace packages.
```

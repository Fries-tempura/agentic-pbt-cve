import io
import os
import tempfile
import zipfile
from pathlib import Path

from hypothesis import given, settings, strategies as st, HealthCheck

from poetry.installation.wheel_installer import WheelDestination, WheelInstaller

segment = st.sampled_from(["..", "pkg", "a", "b", "evil.py"])
rel_paths = st.lists(segment, min_size=1, max_size=6).map("/".join).filter(
    lambda p: not p.endswith("..")
)


def _scheme(root: Path) -> dict:
    d = {k: str(root / "scheme" / k) for k in
         ("purelib", "platlib", "scripts", "data", "headers")}
    for v in d.values():
        os.makedirs(v, exist_ok=True)
    return d


@settings(max_examples=300, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(rel_paths)
def test_write_to_fs_stays_in_scheme(path):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "x" / "y" / "z"
        sd = _scheme(root)
        dest = WheelDestination(sd, interpreter="python", script_kind="posix")
        rec = dest.write_to_fs("purelib", path, io.BytesIO(b"data"), False)
        written = (Path(sd["purelib"]) / rec.path).resolve()
        assert written.is_relative_to(Path(sd["purelib"]).resolve()), written


class FakeEnv:
    def __init__(self, root):
        self.scheme_dict = _scheme(root)
        self.scheme_dict["include"] = str(root / "scheme" / "include")
        self.python = Path("/usr/bin/python3")


def _make_wheel(path: Path, member: str) -> Path:
    whl = path / "demo-1.0-py3-none-any.whl"
    di = "demo-1.0.dist-info"
    files = {
        member: b"pwned\n",
        f"{di}/METADATA": b"Metadata-Version: 2.1\nName: demo\nVersion: 1.0\n",
        f"{di}/WHEEL": b"Wheel-Version: 1.0\nGenerator: x\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    record = "".join(f"{n},,\n" for n in files) + f"{di}/RECORD,,\n"
    with zipfile.ZipFile(whl, "w") as z:
        for n, c in files.items():
            z.writestr(n, c)
        z.writestr(f"{di}/RECORD", record)
    return whl


@settings(max_examples=100, deadline=None)
@given(rel_paths)
def test_install_stays_in_env(member):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        root = tmp / "venv" / "lib" / "site"
        env = FakeEnv(root)
        whl = _make_wheel(tmp, member)
        before = {p for p in tmp.rglob("*")}
        WheelInstaller(env).install(whl)
        new = {p for p in tmp.rglob("*") if p.is_file()} - before
        for p in new:
            assert p.resolve().is_relative_to((root / "scheme").resolve()), p

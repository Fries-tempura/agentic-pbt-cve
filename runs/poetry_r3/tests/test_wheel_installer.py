import base64, hashlib, os, tempfile, zipfile
from pathlib import Path

from hypothesis import given, settings, strategies as st, HealthCheck

from poetry.installation.wheel_installer import WheelInstaller, WheelDestination


class FakeEnv:
    def __init__(self, root: Path):
        self.python = Path("/usr/bin/python3")
        self.scheme_dict = {
            k: str(root / "env" / k)
            for k in ("purelib", "platlib", "scripts", "data", "include")
        }


def rec(name, data):
    h = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"{name},sha256={h},{len(data)}"


def make_wheel(path: Path, files: dict):
    di = "demo-1.0.dist-info"
    meta = {
        f"{di}/METADATA": b"Metadata-Version: 2.1\nName: demo\nVersion: 1.0\n",
        f"{di}/WHEEL": b"Wheel-Version: 1.0\nGenerator: t\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    allf = {**files, **meta}
    lines = [rec(n, d) for n, d in allf.items()] + [f"{di}/RECORD,,"]
    with zipfile.ZipFile(path, "w") as z:
        for n, d in allf.items():
            z.writestr(n, d)
        z.writestr(f"{di}/RECORD", "\n".join(lines) + "\n")


segment = st.sampled_from(["..", "pkg", "a", "b", "."])
member = st.lists(segment, min_size=1, max_size=6).map(lambda s: "/".join(s + ["f.py"]))


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(st.lists(member, min_size=1, max_size=3, unique=True))
def test_install_stays_inside_scheme(members):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        env = FakeEnv(root)
        whl = root / "demo-1.0-py3-none-any.whl"
        make_wheel(whl, {m: b"x = 1\n" for m in members})
        try:
            WheelInstaller(env).install(whl)
        except Exception:
            pass  # rejecting the wheel is acceptable
        envdir = (root / "env").resolve()
        for dirpath, _, fnames in os.walk(root):
            for f in fnames:
                p = (Path(dirpath) / f).resolve()
                if p == whl.resolve():
                    continue
                assert envdir in p.parents, f"file written outside env: {p}"

import base64, hashlib, os, tempfile, zipfile
from pathlib import Path

from hypothesis import given, settings, strategies as st, HealthCheck

from poetry.installation.wheel_installer import WheelInstaller


class FakeEnv:
    def __init__(self, root: Path):
        self.root = root
        self.python = root / "bin" / "python"
        self.scheme_dict = {
            k: str(root / k)
            for k in ("purelib", "platlib", "scripts", "data", "include")
        }


def rec(path, data):
    h = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"{path},sha256={h},{len(data)}"


def build_wheel(dirpath: Path, members):
    whl = dirpath / "demo-1.0-py3-none-any.whl"
    di = "demo-1.0.dist-info"
    files = dict(members)
    files[f"{di}/METADATA"] = b"Metadata-Version: 2.1\nName: demo\nVersion: 1.0\n"
    files[f"{di}/WHEEL"] = b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    record = "\n".join(rec(p, d) for p, d in files.items()) + f"\n{di}/RECORD,,\n"
    with zipfile.ZipFile(whl, "w") as z:
        for p, d in files.items():
            z.writestr(p, d)
        z.writestr(f"{di}/RECORD", record)
    return whl


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

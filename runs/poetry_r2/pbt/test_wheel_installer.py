import io, os, tempfile, zipfile
from pathlib import Path

from hypothesis import given, settings, strategies as st, HealthCheck

from poetry.installation.wheel_installer import WheelDestination, WheelInstaller

SCHEMES = ["purelib", "platlib", "headers", "scripts", "data"]

segment = st.one_of(
    st.just(".."),
    st.text(alphabet="abcxyz_", min_size=1, max_size=5),
)
rel_paths = st.lists(segment, min_size=1, max_size=6).filter(lambda p: p[-1] != "..").map("/".join)


def make_dest(root: Path) -> WheelDestination:
    scheme_dict = {s: str(root / "env" / s) for s in SCHEMES}
    for v in scheme_dict.values():
        os.makedirs(v, exist_ok=True)
    return WheelDestination(scheme_dict, interpreter="/usr/bin/python3", script_kind="posix")


@settings(max_examples=300, suppress_health_check=[HealthCheck.function_scoped_fixture])
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
        assert entry.size == len(data)


class FakeEnv:
    def __init__(self, root: Path):
        self.scheme_dict = {s: str(root / "env" / s) for s in ["purelib", "platlib", "scripts", "data", "include"]}
        self.python = Path("/usr/bin/python3")


def build_wheel(path: Path, member: str, content: bytes) -> None:
    dist = "evil-1.0"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("evil/__init__.py", b"")
        z.writestr(member, content)
        z.writestr(f"{dist}.dist-info/METADATA", "Metadata-Version: 2.1\nName: evil\nVersion: 1.0\n")
        z.writestr(f"{dist}.dist-info/WHEEL", "Wheel-Version: 1.0\nGenerator: x\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        z.writestr(f"{dist}.dist-info/RECORD", "")


@settings(max_examples=50, deadline=None)
@given(depth=st.integers(min_value=1, max_value=4), name=st.text(alphabet="abcxyz", min_size=1, max_size=6))
def test_install_never_writes_outside_env(depth, name):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        wheel = root / "evil-1.0-py3-none-any.whl"
        member = "../" * depth + name + ".txt"
        build_wheel(wheel, member, b"pwned")
        inst = WheelInstaller(FakeEnv(root))
        try:
            inst.install(wheel)
        except Exception:
            pass
        purelib = root / "env" / "purelib"
        escaped = (purelib / member).resolve()
        assert not (escaped.exists() and not escaped.is_relative_to(root / "env")), f"file escaped to {escaped}"

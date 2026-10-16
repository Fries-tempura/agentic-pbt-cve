from __future__ import annotations

import base64
import hashlib
import tempfile
import zipfile

from pathlib import Path

from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from poetry.installation.wheel_installer import WheelInstaller
from poetry.utils.env import MockEnv


segment = st.from_regex(r"[a-z][a-z0-9_]{0,7}", fullmatch=True)
member_path = st.lists(
    st.one_of(segment, st.just("..")), min_size=1, max_size=5
).map(lambda parts: "/".join([*parts, "payload.py"]))


def _record_line(name: str, data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return f"{name},sha256={digest.decode()},{len(data)}"


def build_wheel(path: Path, extra_member: str) -> None:
    files = {
        "demo/__init__.py": b"",
        extra_member: b"x = 1\n",
        "demo-0.1.0.dist-info/METADATA": (
            b"Metadata-Version: 2.1\nName: demo\nVersion: 0.1.0\n"
        ),
        "demo-0.1.0.dist-info/WHEEL": (
            b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\n"
            b"Tag: py3-none-any\n"
        ),
    }
    record = "\n".join(_record_line(n, d) for n, d in files.items())
    record += "\ndemo-0.1.0.dist-info/RECORD,,\n"
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
        zf.writestr("demo-0.1.0.dist-info/RECORD", record)


@settings(max_examples=200, deadline=None)
@given(member_path)
def test_installed_files_stay_inside_scheme_dirs(extra_member: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp).resolve()
        venv = sandbox / "a" / "b" / "c" / "d" / "e" / "venv"
        whl = Path(tmp) / "demo-0.1.0-py3-none-any.whl"
        build_wheel(whl, extra_member)

        env = MockEnv(path=venv)
        WheelInstaller(env).install(whl)

        scheme_dirs = [
            Path(p).resolve()
            for k, p in env.scheme_dict.items()
            if k in ("purelib", "platlib", "scripts", "data")
        ]
        for f in sandbox.rglob("*"):
            if f.is_file() and f != whl.resolve():
                assert any(f.resolve().is_relative_to(d) for d in scheme_dirs), (
                    f"{extra_member!r} was written outside scheme dirs: {f}"
                )

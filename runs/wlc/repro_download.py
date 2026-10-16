import sys, tempfile
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, "/Users/auderyliu/Documents/NTU/project/agentic-pbt-main/dataset/checkouts/CVE-2026-22250__wlc")
from wlc.main import Download

base = Path(tempfile.mkdtemp()).resolve()
out = base / "out"
component = SimpleNamespace(
    project=SimpleNamespace(slug="../escaped"), slug="x", download=lambda convert=None: b"PK"
)
cmd = Download.__new__(Download)
cmd.args = SimpleNamespace(convert=None, output=str(out))
cmd.download_component(component)
print(sorted(str(p.relative_to(base)) for p in base.rglob("*")))

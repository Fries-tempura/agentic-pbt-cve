import io, os, tempfile
from unittest import mock
import wlc
from wlc.main import main

API = "https://weblate.example.org/api/"
tmp = tempfile.mkdtemp()
out = os.path.join(tmp, "out")

def fake_get(self, path, params=None):
    if path.endswith("projects/proj/"):
        return {"url": API + "projects/proj/", "slug": "proj", "name": "p", "web": "", "web_url": "",
                "components_list_url": API + "projects/proj/components/"}
    if path.endswith("projects/proj/components/"):
        return {"next": None, "results": [{
            "url": API + "components/proj/c/", "slug": "c", "name": "c",
            "project": {"url": API + "projects/proj/", "slug": "../../escaped", "name": "p", "web": "", "web_url": ""},
            "is_glossary": False, "category": None,
            "repository_url": API + "components/proj/c/repository/"}]}
    raise AssertionError(path)

with mock.patch.object(wlc.Weblate, "get", fake_get), \
     mock.patch.object(wlc.Weblate, "raw_request", lambda *a, **k: b"PK-evil"):
    main(args=["--url", API, "download", "proj", "-o", out], settings=(), stdout=io.StringIO())

print(os.path.exists(os.path.join(tmp, "..", "escaped-c.zip")), os.path.realpath(os.path.join(out, "../../escaped-c.zip")))
for r, _, fs in os.walk(tmp):
    for f in fs:
        print(os.path.join(r, f))

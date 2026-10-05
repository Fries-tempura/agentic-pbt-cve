import itertools
import os
import posixpath
import tempfile

from mako import exceptions, lookup

BASE = tempfile.mkdtemp(prefix="mako_brute_")
TMPL_DIR = os.path.join(BASE, "app", "templates")
os.makedirs(TMPL_DIR)
open(os.path.join(TMPL_DIR, "index.html"), "w").write("ok")
os.makedirs(os.path.join(BASE, "secrets"))
open(os.path.join(BASE, "secrets", "creds.txt"), "w").write("SECRET")
open(os.path.join(BASE, "app", "app.txt"), "w").write("APP")


def inside(f, d):
    f = posixpath.normpath(os.path.abspath(f))
    d = posixpath.normpath(os.path.abspath(d))
    return f == d or f.startswith(d + "/")


SEGS = ["..", ".", "", "app", "templates", "secrets", "creds.txt", "app.txt"]
escapes = []
n = 0
for nslash in range(4):
    for length in range(1, 6):
        for combo in itertools.product(SEGS, repeat=length):
            uri = "/" * nslash + "/".join(combo)
            n += 1
            tl = lookup.TemplateLookup(directories=[TMPL_DIR])
            try:
                t = tl.get_template(uri)
            except exceptions.TemplateLookupException:
                continue
            except Exception as e:
                escapes.append((uri, "UNEXPECTED " + repr(e)))
                continue
            if not inside(t.filename, TMPL_DIR):
                escapes.append((uri, t.filename))

print(f"tried {n} uris; escapes: {len(escapes)}")
for e in escapes[:20]:
    print(e)

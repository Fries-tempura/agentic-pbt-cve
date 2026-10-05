import os
import tempfile

from mako import lookup

base = tempfile.mkdtemp()
tmpl_dir = os.path.join(base, "app", "templates")
os.makedirs(tmpl_dir)
open(os.path.join(tmpl_dir, "index.html"), "w").write("Hello")
secret_dir = os.path.join(base, "secrets")
os.makedirs(secret_dir)
open(os.path.join(secret_dir, "creds.txt"), "w").write("SECRET=supersecret123")

tl = lookup.TemplateLookup(directories=[tmpl_dir])
rel = os.path.relpath(os.path.join(secret_dir, "creds.txt"), tmpl_dir)
print("rel:", rel)
for prefix in ["", "/", "//", "///", "/./", "/x/../../"]:
    uri = prefix + rel
    tl2 = lookup.TemplateLookup(directories=[tmpl_dir])
    try:
        t = tl2.get_template(uri)
        print(repr(uri), "-> LOADED", t.filename, "|", repr(t.render()))
    except Exception as e:
        print(repr(uri), "->", type(e).__name__, e)

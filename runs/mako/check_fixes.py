import posixpath

from mako import lookup


def fixed_adjust_uri(self, uri, relativeto):
    key = (uri, relativeto)
    if key in self._uri_cache:
        return self._uri_cache[key]
    if uri.startswith("/"):
        v = self._uri_cache[key] = uri
    elif relativeto is not None:
        v = self._uri_cache[key] = posixpath.join(
            posixpath.dirname(relativeto), uri
        )
    else:
        v = self._uri_cache[key] = "/" + uri
    return v


def fixed_relativeize(self, filename):
    filename = posixpath.normpath(filename)
    for dir_ in self.directories:
        dir_ = dir_.rstrip("/")
        if filename == dir_:
            return ""
        if filename.startswith(dir_ + "/"):
            return filename[len(dir_) :]
    return None


lookup.TemplateLookup.adjust_uri = fixed_adjust_uri
lookup.TemplateLookup._relativeize = fixed_relativeize

tl = lookup.TemplateLookup(directories=["."])
tl.put_string("index.html", "<%include file='${name}'/>")
try:
    tl.get_template("index.html").render(name="")
except Exception as e:
    print("empty include ->", type(e).__name__)

tl = lookup.TemplateLookup(directories=["/srv/templates"])
print("sibling dir ->", repr(tl.filename_to_uri("/srv/templates_backup/x.html")))

# existing test_uri_adjust expectations must still hold
tl = lookup.TemplateLookup(directories=["/foo/bar"])
assert tl.filename_to_uri("/foo/bar/etc/lala/index.html") == "/etc/lala/index.html"
tl = lookup.TemplateLookup(directories=["./foo/bar"])
assert tl.filename_to_uri("./foo/bar/etc/index.html") == "/etc/index.html"
print("existing test_uri_adjust expectations: OK")

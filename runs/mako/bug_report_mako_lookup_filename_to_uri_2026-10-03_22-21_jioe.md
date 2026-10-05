# Bug Report: mako.lookup.TemplateLookup.filename_to_uri matches directory prefixes, not directory boundaries

**Target**: `mako.lookup.TemplateLookup.filename_to_uri` / `TemplateLookup._relativeize`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-03

## Summary

`_relativeize` tests directory membership with a raw string-prefix comparison
(`filename[0:len(dir_)] == dir_`) instead of a path-component comparison. A file
that merely *starts with* a lookup directory's name — e.g.
`/srv/templates_backup/secret.html` against the lookup directory
`/srv/templates` — is silently reported as belonging to that directory, and
`filename_to_uri` returns a mangled URI (`_backup/secret.html`) instead of
`None`.

## Property-Based Test

```python
import posixpath

from hypothesis import assume, given, settings, strategies as st

from mako import lookup

dirnames = st.lists(
    st.sampled_from(["foo", "bar", "baz"]), min_size=1, max_size=3
).map(lambda s: "/" + "/".join(s))
names = st.text(alphabet="abz_-", min_size=1, max_size=4)


@settings(max_examples=1000)
@given(dirnames, names, names)
def test_filename_to_uri_only_claims_files_under_a_directory(
    directory, sibling_suffix, leaf
):
    """If filename_to_uri returns a uri for a filename, then joining that
    uri back onto the lookup directory must give the original filename."""
    assume(sibling_suffix != "")
    tl = lookup.TemplateLookup(directories=[directory])
    filename = directory + sibling_suffix + "/" + leaf + ".html"

    uri = tl.filename_to_uri(filename)
    if uri is None:
        return
    rejoined = posixpath.normpath(posixpath.join(directory, uri.lstrip("/")))
    assert rejoined == posixpath.normpath(filename)
```

**Failing input**: `directory='/foo'`, `sibling_suffix='_'`, `leaf='_'`
(i.e. `directories=['/foo']`, `filename='/foo_/_.html'` → `uri='_/_.html'`,
which maps back to `/foo/_/_.html`, a different file)

## Reproducing the Bug

```python
from mako.lookup import TemplateLookup

tl = TemplateLookup(directories=["/srv/templates"])
print(tl.filename_to_uri("/srv/templates_backup/secret.html"))
```

```
_backup/secret.html
```

Expected `None`: `/srv/templates_backup/secret.html` is not inside
`/srv/templates`.

## Why This Is A Bug

`filename_to_uri` is documented as "Convert the given `filename` to a URI
relative to this `TemplateCollection`", and `_relativeize` as "Return the
portion of a filename that is 'relative' to the directories in this lookup."
`/srv/templates_backup/secret.html` has no portion relative to
`/srv/templates` — the two are sibling directories, not parent and child — so
the documented contract calls for the `None` that `_relativeize`'s `else` branch
is there to return.

Instead the function silently produces a URI that is wrong in two ways: it is
not a valid URI for the input file, and feeding it back through
`get_template` resolves to a *different* file under the real lookup directory
(`/srv/templates/_backup/secret.html`), so the round-trip
`filename_to_uri` → `get_template` is broken.

Sibling directories sharing a prefix are ordinary deployment layouts
(`templates` / `templates_admin`, `templates` / `templates.bak`,
`/app/tmpl` / `/app/tmpl2`), and the breakage is silent — no exception, just a
wrong URI. The same prefix comparison also mis-handles the multi-directory case:
with `directories=["/srv/tmpl", "/srv/tmpl_admin"]`, every file under
`/srv/tmpl_admin` is claimed by the first directory, because the loop returns on
the first prefix match.

## Fix

Require the match to end on a path separator (or be the directory itself):

```diff
--- a/mako/lookup.py
+++ b/mako/lookup.py
@@ -289,10 +289,13 @@ class TemplateLookup(TemplateCollection):
 
         filename = posixpath.normpath(filename)
         for dir_ in self.directories:
-            if filename[0 : len(dir_)] == dir_:
-                return filename[len(dir_) :]
+            dir_ = dir_.rstrip("/")
+            if filename == dir_:
+                return ""
+            if filename.startswith(dir_ + "/"):
+                return filename[len(dir_) :]
         else:
             return None
```

Verified: with this patch the reproduction returns `None`, and the existing
`test_lookup.py::test_uri_adjust` expectations
(`filename_to_uri("/foo/bar/etc/lala/index.html") == "/etc/lala/index.html"` and
`filename_to_uri("./foo/bar/etc/index.html") == "/etc/index.html"`) still hold.

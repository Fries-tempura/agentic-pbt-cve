# Bug Report: mako.lookup.TemplateLookup.adjust_uri IndexError on empty URI

**Target**: `mako.lookup.TemplateLookup.adjust_uri`
**Severity**: Low
**Bug Type**: Crash
**Date**: 2026-10-03

## Summary

`TemplateLookup.adjust_uri("")` raises `IndexError: string index out of range`
instead of a `mako.exceptions.TemplateLookupException`. The failure escapes to
template rendering, so an `<%include file="${expr}"/>` whose expression
evaluates to the empty string crashes with a non-Mako exception that
template-error handlers (which catch `mako.exceptions.MakoException`) will not
catch.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st

from mako import exceptions
from mako import lookup


@settings(max_examples=500)
@given(st.text(max_size=20), st.one_of(st.none(), st.text(max_size=20)))
def test_adjust_uri_no_unexpected_crash(uri, relativeto):
    tl = lookup.TemplateLookup(directories=[TMPL_DIR])
    try:
        result = tl.adjust_uri(uri, relativeto)
    except exceptions.MakoException:
        return
    assert isinstance(result, str)
```

**Failing input**: `uri=''`, `relativeto='..'` (any `relativeto`, including `None`)

## Reproducing the Bug

```python
from mako.lookup import TemplateLookup

tl = TemplateLookup(directories=["."])
tl.put_string("index.html", "<%include file='${name}'/>")
tl.get_template("index.html").render(name="")
```

```
  File "mako/runtime.py", line 835, in _lookup_template
    uri = lookup.adjust_uri(uri, relativeto)
  File "mako/lookup.py", line 264, in adjust_uri
    if uri[0] == "/":
       ~~~^^^
IndexError: string index out of range
```

## Why This Is A Bug

`adjust_uri` is public API inherited from `TemplateCollection`, and it is the
first thing `mako.runtime._lookup_template` calls for every `<%include>`,
`<%namespace>` and `<%inherit>` resolution. `TemplateCollection.get_template`
documents that "Implementations should raise `TemplateLookupException` if the
given `uri` cannot be resolved" — an empty URI cannot be resolved, so the
documented `TemplateLookupException` is the expected outcome. Every other
unresolvable URI (`"nonexistent.html"`, `"/subdir"`, `"../.."`) does raise
`TemplateLookupException`; only the empty string produces a bare `IndexError`.

Because `IndexError` is not a `MakoException`, applications that wrap rendering
in `except mako.exceptions.MakoException` to render a template-error page will
let this one propagate as an unhandled server error instead.

## Fix

`uri.startswith("/")` is the empty-string-safe form of the same test. With it,
`adjust_uri("")` falls through to the existing branches and yields `"/"` (or the
`relativeto` directory), which `get_template` then rejects with
`TopLevelLookupException`, a `TemplateLookupException` subclass.

```diff
--- a/mako/lookup.py
+++ b/mako/lookup.py
@@ -261,7 +261,7 @@ class TemplateLookup(TemplateCollection):
         if key in self._uri_cache:
             return self._uri_cache[key]
 
-        if uri[0] == "/":
+        if uri.startswith("/"):
             v = self._uri_cache[key] = uri
         elif relativeto is not None:
             v = self._uri_cache[key] = posixpath.join(
```

Verified: with this patch the reproduction above raises
`mako.exceptions.TemplateLookupException`, and the existing `test_uri_adjust` /
`test_lookup.py` expectations are unaffected.

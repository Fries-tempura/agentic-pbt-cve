# Bug Report: pypdf._reader PdfReader.root_object raises AttributeError when /Root is not a dictionary

**Target**: `pypdf._reader.PdfReader.root_object`
**Severity**: Medium
**Bug Type**: Crash

## Summary

`root_object` calls `.get("/Type")` on whatever `/Root` resolves to without first
checking it is a dictionary. If `/Root` points to a non-dictionary object (e.g. a number),
the property raises a bare `AttributeError` instead of a `pypdf` error. This leaks through
`len(reader.pages)`, `reader.metadata`, and other high-level calls.

## Property-Based Test

```python
@given(st.data())
@settings(max_examples=500, deadline=None, suppress_health_check=list(HealthCheck))
def test_corrupt_bytes_only_pypdf_errors(data):
    pdf = bytearray(build_pdf([CATALOG, PAGES, PAGE % (100, 100)]))
    for _ in range(data.draw(st.integers(1, 4))):
        pos = data.draw(st.integers(0, len(pdf) - 1))
        op = data.draw(st.sampled_from(["set", "del", "ins"]))
        b = data.draw(st.sampled_from(list(b"0123456789 \n\rxreftailo<>/[]R%")))
        if op == "set":
            pdf[pos] = b
        elif op == "del":
            del pdf[pos]
        else:
            pdf.insert(pos, b)
    try:
        r = PdfReader(io.BytesIO(bytes(pdf)))
        for p in r.pages:
            p.mediabox
    except PyPdfError:
        return
```

**Failing input**: a single-byte mutation that makes object 1 parse as a number, so the
trailer's `/Root 1 0 R` resolves to a `NumberObject`.

## Reproducing the Bug

```python
import io
from pypdf import PdfReader

def build(objs):
    out = bytearray(b"%PDF-1.7\n"); offs = []
    for i, body in enumerate(objs, 1):
        offs.append(len(out)); out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offs:
        out += b"%010d 00000 n \n" % o
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
    return bytes(out)

data = build([b"42", b"<< /Type /Pages /Kids [] /Count 0 >>"])
r = PdfReader(io.BytesIO(data))
r.root_object
```

Raises `AttributeError: 'NumberObject' object has no attribute 'get'`.

## Why This Is A Bug

`root_object` is documented public API. For malformed input it is expected to either
recover or raise a `PdfReadError` (a `PyPdfError` subclass), which callers catch. A bare
`AttributeError` is undocumented and bypasses `except PyPdfError` handlers. The sibling
property `_info` already guards against this by checking `isinstance(..., DictionaryObject)`
and raising `PdfReadError`; `root_object` does not.

## Fix

Guard both places that assume `/Root` resolves to a dictionary (the `/Type` lookup and
the later `/Pages` membership test, which would otherwise raise a `TypeError` instead):

```diff
         root = self.trailer.get(TK.ROOT)
         if is_null_or_none(root):
             logger_warning('Cannot find "/Root" key in trailer', __name__)
-        elif (
-            cast(DictionaryObject, cast(PdfObject, root).get_object()).get("/Type")
-            == "/Catalog"
-        ):
+        elif (
+            isinstance(cast(PdfObject, root).get_object(), DictionaryObject)
+            and cast(DictionaryObject, cast(PdfObject, root).get_object()).get("/Type")
+            == "/Catalog"
+        ):
             self._validated_root = cast(
                 DictionaryObject, cast(PdfObject, root).get_object()
             )
@@
         if self._validated_root is None:
-            if not is_null_or_none(root) and "/Pages" in cast(DictionaryObject, cast(PdfObject, root).get_object()):
+            if (
+                not is_null_or_none(root)
+                and isinstance(cast(PdfObject, root).get_object(), DictionaryObject)
+                and "/Pages" in cast(DictionaryObject, cast(PdfObject, root).get_object())
+            ):
```

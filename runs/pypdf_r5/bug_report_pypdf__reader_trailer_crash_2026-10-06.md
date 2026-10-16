# Bug Report: pypdf._reader raises raw AttributeError/TypeError on malformed trailer

**Target**: `pypdf._reader.PdfReader.read` (via `_read_xref` / `root_object`)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-06

## Summary

`PdfReader` documents and otherwise signals parse failures through `PdfReadError`
(a `PyPdfError` subclass), and in non-strict mode tries hard to recover from broken
files. But several malformed-but-plausible inputs escape as raw built-in exceptions
(`AttributeError`, `TypeError`), which a caller guarding against `PyPdfError` will not
catch. Two concrete cases:

1. A trailer whose value is a non-dictionary object (e.g. `trailer\n1 << ... >>`)
   makes `_read_xref` do `new_trailer.items()` on a `NumberObject`
   -> `AttributeError: 'NumberObject' object has no attribute 'items'`.
2. A `/Size` entry that is not an integer reaches `root_object`'s
   `for i in range(nb)` -> `TypeError: 'NameObject' object cannot be interpreted as
   an integer`.

## Property-Based Test

```python
@given(st.data())
def test_mutated_pdf_no_unexpected_exceptions(data):
    w = PdfWriter(); w.add_blank_page(100, 100); w.add_blank_page(100, 100)
    buf = io.BytesIO(); w.write(buf)
    b = bytearray(buf.getvalue())
    for _ in range(data.draw(st.integers(1, 5))):
        pos = data.draw(st.integers(0, len(b) - 1))
        b[pos] = data.draw(st.integers(0, 255))
    try:
        r = PdfReader(io.BytesIO(bytes(b)))
        len(r.pages)
    except PyPdfError:
        pass   # only pypdf's own error hierarchy is acceptable
```

**Failing input**: single-byte mutations of a valid 2-page PDF, e.g. one that turns
`trailer\n<<` into a non-dict value, or corrupts `/Size`'s value.

## Reproducing the Bug

```python
import io
from pypdf import PdfReader, PdfWriter

w = PdfWriter(); w.add_blank_page(100, 100)
buf = io.BytesIO(); w.write(buf)
good = buf.getvalue()

cases = {
    "trailer not a dict": good.replace(b"trailer\n<<", b"trailer\n1 <<"),
    "/Size not int":      good.replace(b"/Root", b"/Rxxt").replace(b"/Size ", b"/Size /X %"),
}
for name, data in cases.items():
    try:
        PdfReader(io.BytesIO(data))
        print(name, "OK")
    except Exception as e:
        print(name, "->", type(e).__name__, e)
```

Output:
```
trailer not a dict -> AttributeError 'NumberObject' object has no attribute 'items'
/Size not int -> TypeError 'NameObject' object cannot be interpreted as an integer
```

## Why This Is A Bug

pypdf's contract for corrupt files is to raise `PdfReadError` (non-strict mode even
tries to recover rather than raise). Leaking `AttributeError`/`TypeError` from internal
parsing breaks that contract: callers that wrap `PdfReader` in `except PyPdfError`
(the documented pattern) will see these propagate as unexpected crashes.

## Fix

Validate the parsed objects before use and raise `PdfReadError`:

```diff
--- a/pypdf/_reader.py
+++ b/pypdf/_reader.py
@@ def _read_xref(self, stream):
         new_trailer = cast(dict[str, Any], read_object(stream, self))
+        if not isinstance(new_trailer, DictionaryObject):
+            raise PdfReadError("Trailer is not a dictionary")
         for key, value in new_trailer.items():
@@ def root_object(self):
-            nb = cast(int, self.trailer.get("/Size", 0))
+            nb = self.trailer.get("/Size", 0)
+            if not isinstance(nb, int):
+                nb = 0
             for i in range(nb):
```

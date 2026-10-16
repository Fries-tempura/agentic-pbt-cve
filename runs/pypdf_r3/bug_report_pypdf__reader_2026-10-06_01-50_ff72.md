# Bug Report: pypdf._reader PdfReader.root_object scales with trailer /Size when /Root is absent

**Target**: `pypdf._reader.PdfReader.root_object`
**Severity**: Medium
**Bug Type**: Logic

## Summary

When the trailer lacks a valid `/Root`, `root_object` falls back to scanning every
object number in `range(trailer["/Size"])`. `/Size` is read directly from the file and
is never validated, and each absent object number triggers a full-file regex search in
`get_object`. Runtime therefore scales as O(`/Size` × file length), so a small
malformed PDF can make `root_object` (and anything that calls it, such as
`len(reader.pages)`) take minutes to hours.

## Property-Based Test

```python
@given(st.integers(0, 10**9))
@settings(max_examples=30, deadline=None)
def test_missing_root_bounded_time(size):
    data = build_pdf([CATALOG.replace(b"/Catalog", b"/Foo"), PAGES, PAGE % (10, 10)],
                     include_root=False, size=size)
    r = PdfReader(io.BytesIO(data))
    t = time.time()
    try:
        r.root_object
    except PyPdfError:
        pass
    assert time.time() - t < 2.0
```

**Failing input**: `size` around 100000 and above.

## Reproducing the Bug

```python
import io, time
from pypdf import PdfReader

def build(objs, size):
    out = bytearray(b"%PDF-1.7\n"); offs = []
    for i, body in enumerate(objs, 1):
        offs.append(len(out)); out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offs:
        out += b"%010d 00000 n \n" % o
    out += b"trailer\n<< /Size %d >>\nstartxref\n%d\n%%%%EOF\n" % (size, x)
    return bytes(out)

for size in (10, 1000, 10000, 100000):
    r = PdfReader(io.BytesIO(build([b"<< /Type /Foo >>"], size)))
    t = time.time()
    try:
        r.root_object
    except Exception as e:
        err = type(e).__name__
    print(size, round(time.time() - t, 2), "s", err)
```

Measured on a 222-byte file: `/Size` 10 -> 0.00 s, 1000 -> 0.03 s, 10000 -> 0.33 s,
100000 -> 2.55 s (linear in `/Size`). A 1 MB file with `/Size 2000` takes 34 s, since
the regex search cost per missing object is proportional to file length.

## Why This Is A Bug

`/Size` is untrusted and the fallback catalog search has no upper bound on the work it
does. For every object number not present in the xref, `get_object` scans the whole file
buffer with `re.search` and logs a warning. The scan only needs to consider object
numbers that actually exist in the parsed xref/object-stream maps, not every integer up
to `/Size`.

## Fix

Iterate only over object numbers that were actually parsed from the xref tables and
object streams instead of `range(/Size)`:

```diff
         if self._validated_root is None:
             logger_warning('Searching object with "/Catalog" key', __name__)
-            nb = cast(int, self.trailer.get("/Size", 0))
-            for i in range(nb):
+            candidates = set(self.xref_objStm)
+            for entry in self.xref.values():
+                candidates.update(entry)
+            for num in sorted(candidates):
                 try:
-                    o = self.get_object(i + 1)
+                    o = self.get_object(num)
                 except Exception:  # to be sure to capture all errors
                     o = None
                 if isinstance(o, DictionaryObject) and o.get("/Type") == "/Catalog":
                     self._validated_root = o
                     logger_warning(f"Root found at {o.indirect_reference!r}", __name__)
                     break
```

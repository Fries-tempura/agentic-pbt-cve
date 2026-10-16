# Bug Report: pypdf._reader unbounded loop over xref-stream /Size

**Target**: `pypdf._reader.PdfReader._read_pdf15_xref_stream` / `_read_xref_subsections`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

When reading a cross-reference stream, `PdfReader` loops once per object number in
`/Index` (default `[0 /Size]`) without checking that the decoded stream actually
contains that many entries. Once the stream data runs out, `get_entry` reads `b""`
and `convert_to_int` returns `0`, so the loop happily continues treating the rest as
free entries. A small file (~400 bytes) that declares a huge `/Size` makes
`PdfReader(...)` run far longer than its real content justifies — parse time scales
with the declared integer, not the file size.

## Property-Based Test

```python
@settings(max_examples=30, deadline=None)
@given(st.integers(min_value=4, max_value=2**40))
def test_xref_stream_size_terminates_quickly(size):
    data = build_xref_stream_pdf(size)   # valid 4-entry xref stream; only /Size varies
    t = time.time()
    try:
        r = PdfReader(io.BytesIO(data))
        len(r.pages)
    except PyPdfError:
        pass
    assert time.time() - t < 5
```

**Failing input**: `size=1067018` (any value above ~10^6 exceeds the budget; parse
time grows linearly at ~0.55 µs per declared entry).

## Reproducing the Bug

```python
import io, time, zlib
from pypdf import PdfReader

def make_pdf(size):
    head = b"%PDF-1.5\n"
    o1 = len(head); obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    o2 = o1 + len(obj1); obj2 = b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    o3 = o2 + len(obj2)
    rows = b"".join(bytes([1]) + o.to_bytes(2, "big") + b"\x00" for o in (0, o1, o2, o3))
    data = zlib.compress(rows)
    xref = (b"3 0 obj\n<< /Type /XRef /Size %d /W [1 2 1] /Root 1 0 R /Filter /FlateDecode /Length %d >>\nstream\n"
            % (size, len(data)) + data + b"\nendstream\nendobj\nstartxref\n%d\n%%%%EOF\n" % o3)
    return head + obj1 + obj2 + xref

for size in (10**5, 10**6, 10**7):
    t = time.time()
    PdfReader(io.BytesIO(make_pdf(size)))
    print(size, f"{time.time() - t:.2f}s")
```

Measured: `100000 -> 0.06s`, `1000000 -> 0.55s`, `10000000 -> 5.61s`. The file stays
under 400 bytes regardless of the declared `/Size`.

## Why This Is A Bug

The decoded xref stream holds only 4 four-byte entries, which already proves the
declared `/Size` is wrong. Parsing cost should be bounded by the actual input, not by
an integer the file declares. `PdfReader` is routinely pointed at untrusted PDFs, so
unbounded work driven by a declared field is a robustness defect.

## Fix

Bound the subsection iteration by the amount of data actually present in the decoded
stream (number of entries = `len(data) // sum(entry_sizes)`), and warn/raise when the
declared `/Index`/`/Size` exceeds it.

```diff
--- a/pypdf/_reader.py
+++ b/pypdf/_reader.py
@@ def _read_pdf15_xref_stream(
-        stream_data = BytesIO(xrefstream.get_data())
+        data = xrefstream.get_data()
+        stream_data = BytesIO(data)
+        entry_width = sum(entry_sizes[:3])
+        available = len(data) // entry_width if entry_width else 0
+        declared = sum(size for _, size in self._pairs(idx_pairs))
+        if declared > available:
+            if self.strict:
+                raise PdfReadError("XRef stream /Index/Size exceeds available data")
+            logger_warning("XRef stream /Index/Size exceeds available data", __name__)
```

# Bug Report: pypdf._reader Unbounded DoS via attacker-controlled `/Size` in `root_object` fallback

**Target**: `pypdf._reader.PdfReader.root_object`
**Severity**: High
**Bug Type**: Crash (resource-exhaustion / denial of service)
**Date**: 2026-10-06

## Summary

When a PDF has no valid `/Root` entry, `PdfReader.root_object` falls back to brute-force
searching for a `/Catalog` object by looping `for i in range(self.trailer["/Size"])`. The
`/Size` value is fully attacker-controlled from the trailer and is never bounded by the file
length. Each iteration calls `get_object`, which compiles a fresh regex and scans the entire
buffer, giving `O(/Size × filesize)` work. A ~150-byte file declaring `/Size 1000000` hangs
for ~18 seconds; a larger `/Size` makes the time grow without bound.

## Property-Based Test

```python
import io, time
from hypothesis import given, settings, strategies as st, HealthCheck
from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError

def build_pdf(objs, trailer):
    out = io.BytesIO(); out.write(b"%PDF-1.4\n"); offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(out.tell()); out.write(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for o in offsets:
        out.write(b"%010d 00000 n \n" % o)
    out.write(b"trailer\n<< " + trailer + b" >>\nstartxref\n%d\n%%%%EOF\n" % xref)
    return out.getvalue()

@settings(max_examples=30, deadline=None, suppress_health_check=list(HealthCheck))
@given(size=st.integers(0, 10**7))
def test_missing_root_large_size_runtime(size):
    data = build_pdf([b"<< /Type /Pages /Kids [] /Count 0 >>"], b"/Size %d" % size)
    t = time.perf_counter()
    try:
        r = PdfReader(io.BytesIO(data)); len(r.pages)
    except (PdfReadError, PdfStreamError):
        pass
    el = time.perf_counter() - t
    assert el < 2.0, f"{len(data)}-byte file took {el:.1f}s with /Size {size}"
```

**Failing input**: `size=300000` (a 156-byte file; any large `/Size` fails)

## Reproducing the Bug

```python
import io, time, logging
logging.disable(logging.CRITICAL)
from pypdf import PdfReader

data = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    b"xref\n0 2\n0000000000 65535 f \n0000000009 00000 n \n"
    b"trailer\n<< /Size 1000000 >>\n"
    b"startxref\n61\n%%EOF\n"
)
reader = PdfReader(io.BytesIO(data))
t = time.perf_counter()
try:
    len(reader.pages)
except Exception as e:
    print("raised:", type(e).__name__)
print(f"{len(data)}-byte file, /Size 1000000: {time.perf_counter() - t:.1f}s")
```

Observed: the ~150-byte file blocks for ~18s before raising `Cannot find Root object in pdf`.
Time scales linearly with `/Size` (`/Size 100000` ≈ 1.7s, `/Size 1000000` ≈ 18s).

## Why This Is A Bug

`/Size` is an untrusted value read directly from the PDF trailer. The fallback loop treats it
as a trustworthy object count and performs a full-buffer regex search per index, with no
relationship to the actual file size or any iteration cap. A tiny malicious or corrupt file
can therefore consume unbounded CPU and wall-clock time inside a single `len(reader.pages)`
(or any other `root_object`) call — a classic amplification DoS against any service that opens
untrusted PDFs with pypdf. This matches the triage criteria for a genuine bug: the input is a
realistic malformed PDF, the value is attacker-controlled, and the cost is grossly
disproportionate to the input.

## Fix

Bound the brute-force search by the actual number of object offsets discovered while parsing
the xref, instead of the untrusted `/Size`, so the loop can never exceed what the file could
plausibly contain.

```diff
--- a/pypdf/_reader.py
+++ b/pypdf/_reader.py
@@ def root_object
             logger_warning('Searching object with "/Catalog" key', __name__)
-            nb = cast(int, self.trailer.get("/Size", 0))
-            for i in range(nb):
+            # /Size is attacker-controlled and unbounded; never scan more
+            # objects than the xref actually references (cf. DoS on tiny files
+            # declaring a huge /Size).
+            known_ids = {idnum for gen in self.xref.values() for idnum in gen}
+            known_ids |= set(self.xref_objStm)
+            nb = cast(int, self.trailer.get("/Size", 0))
+            if known_ids:
+                nb = min(nb, max(known_ids) + 1)
+            for i in range(nb):
                 try:
                     o = self.get_object(i + 1)
```

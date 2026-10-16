# Bug Report: pypdf._reader Unbounded `/Root` Search Driven by Attacker-Controlled `/Size`

**Target**: `pypdf._reader.PdfReader.root_object`
**Severity**: Medium
**Bug Type**: Logic (resource-exhaustion / DoS amplification)
**Date**: 2026-10-06

## Summary

When a PDF has no valid `/Root` entry, `root_object` falls back to a linear scan
`for i in range(nb)` where `nb = trailer["/Size"]`, calling `get_object(i + 1)` on
every id. `/Size` is attacker-controlled and unrelated to the real file length, so a
157-byte file declaring `/Size 1000000` forces ~1,000,000 object lookups (~22 s of CPU)
before raising `PdfReadError("Cannot find Root object in pdf")`.

## Property-Based Test

```python
import io, time
from hypothesis import given, settings
from hypothesis import strategies as st
from pypdf import PdfReader
from pypdf.errors import PdfReadError

def build(size):
    out = b"%PDF-1.7\n"; off = len(out)
    out += b"1 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    xref = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref)
    return out

@settings(max_examples=20, deadline=None)
@given(st.integers(min_value=10**5, max_value=10**7))
def test_missing_root_bounded_time(size):
    r = PdfReader(io.BytesIO(build(size)))
    t = time.perf_counter()
    try:
        len(r.pages)
    except PdfReadError:
        pass
    assert time.perf_counter() - t < 2.0, f"took too long for /Size {size}"
```

**Failing input**: `size = 1000000` (any large `/Size`; a 157-byte file)

## Reproducing the Bug

```python
import io, time
from pypdf import PdfReader

out = b"%PDF-1.7\n"
off = len(out)
out += b"1 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
xref = len(out)
out += b"xref\n0 2\n0000000000 65535 f \n%010d 00000 n \n" % off
out += b"trailer\n<< /Size %d >>\nstartxref\n%d\n%%%%EOF\n" % (10**6, xref)

print("file size:", len(out), "bytes")
r = PdfReader(io.BytesIO(out))
t = time.perf_counter()
try:
    len(r.pages)
except Exception as e:
    print("raised", type(e).__name__)
print("elapsed:", round(time.perf_counter() - t, 1), "s")
```

Output: `file size: 157 bytes` ... `elapsed: 22.0 s`.

## Why This Is A Bug

`/Size` is a value taken verbatim from the (untrusted) PDF trailer and bounds the number
of real objects, but it is in no way bounded by the actual file size. The fallback search
in `root_object` treats it as an iteration count:

```python
nb = cast(int, self.trailer.get("/Size", 0))
for i in range(nb):
    try:
        o = self.get_object(i + 1)
    ...
```

This yields a ~140,000× work amplification (157 bytes → 22 s), and the cost grows linearly
without limit as `/Size` grows. A malformed/malicious document a few hundred bytes long can
pin a CPU for minutes, which is a denial-of-service vector for any service that opens
untrusted PDFs. The search should be bounded by the number of objects actually present in
the file (e.g. `self.xref` / `self.xref_objStm`) rather than the declared `/Size`.

## Fix

Limit the recovery scan to object ids the parser has actually located, instead of the
attacker-declared `/Size`:

```diff
         if self._validated_root is None:
             logger_warning('Searching object with "/Catalog" key', __name__)
-            nb = cast(int, self.trailer.get("/Size", 0))
-            for i in range(nb):
+            candidate_ids = sorted(
+                {num for entry in self.xref.values() for num in entry}
+                | set(self.xref_objStm)
+            )
+            for i in candidate_ids:
                 try:
-                    o = self.get_object(i + 1)
+                    o = self.get_object(i)
                 except Exception:  # to be sure to capture all errors
                     o = None
                 if isinstance(o, DictionaryObject) and o.get("/Type") == "/Catalog":
                     self._validated_root = o
                     logger_warning(f"Root found at {o.indirect_reference!r}", __name__)
                     break
```

# Bug Report: pypdf._reader Unbounded loop on attacker-controlled XRef stream /Size

**Target**: `pypdf._reader.PdfReader` (`_read_pdf15_xref_stream` / `_read_xref_subsections`)
**Severity**: Medium
**Bug Type**: Crash (denial of service)
**Date**: 2026-10-05

## Summary

When reading a PDF 1.5+ cross-reference stream, `PdfReader` trusts the `/Size`
(and `/Index`) values from the xref stream dictionary and iterates
`range(start, start + size)` over them, regardless of how much data the stream
actually contains. A tiny (~320 byte) PDF that declares a huge `/Size` makes
`PdfReader` spin in that loop, so parse time grows linearly with the attacker's
declared value while file size stays constant — an amplified denial of service.

## Property-Based Test

```python
import time
from io import BytesIO
from hypothesis import given, settings, strategies as st
from pypdf import PdfReader
from test_reader_pbt import make_xref_stream_pdf  # builds a valid ~320B xref-stream PDF


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=6, max_value=2**31 - 1))
def test_xref_stream_size_does_not_blow_up(size):
    pdf = make_xref_stream_pdf(size)
    t = time.perf_counter()
    r = PdfReader(BytesIO(pdf))
    elapsed = time.perf_counter() - t
    assert len(r.pages) == 1
    assert elapsed < 2.0, (size, elapsed)
```

**Failing input**: any large `size`, e.g. `size = 10_000_000` (324-byte PDF, ~5.5 s);
`size = 2**31 - 1` runs for roughly 20 minutes.

## Reproducing the Bug

```python
import time
from io import BytesIO
from pypdf import PdfReader


def make_pdf(size):
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 10 10] >>",
    ]
    out = bytearray(b"%PDF-1.5\n")
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref_off = len(out)
    rows = [bytes([0, 0, 0, 0xFF])]
    for off in offsets + [xref_off]:
        rows.append(bytes([1]) + off.to_bytes(2, "big") + bytes([0]))
    data = b"".join(rows)
    out += (
        b"5 0 obj\n<< /Type /XRef /Size %d /W [1 2 1] /Root 1 0 R /Length %d >>\nstream\n"
        % (size, len(data))
    )
    out += data + b"\nendstream\nendobj\n"
    out += b"startxref\n%d\n%%%%EOF\n" % xref_off
    return bytes(out)


pdf = make_pdf(10_000_000)
print("file size:", len(pdf))
t = time.perf_counter()
PdfReader(BytesIO(pdf))
print("parse time:", time.perf_counter() - t)
```

Measured scaling (324-byte file, varying only `/Size`):

| /Size        | parse time |
|--------------|------------|
| 6            | ~0.000 s   |
| 100,000      | 0.054 s    |
| 1,000,000    | 0.536 s    |
| 10,000,000   | 5.513 s    |

Time is linear in the declared `/Size`; the file itself stays ~320 bytes.

## Why This Is A Bug

`PdfReader` is routinely used on untrusted input (uploaded PDFs, email
attachments, crawled documents). `_read_pdf15_xref_stream` takes
`idx_pairs = xrefstream.get("/Index", [0, xrefstream["/Size"]])` and
`_read_xref_subsections` loops `for num in range(start, start + size)`, calling
`get_entry` on each iteration. There is no check that `size` is consistent with
the amount of data in the decoded xref stream (`stream_data`). Once the real
data is exhausted, `get_entry` keeps returning `0`/defaults, so the loop simply
burns CPU for the full declared count. A ~320 byte file can therefore pin a CPU
for many minutes — a classic decompression/amplification DoS.

## Fix

Bound the number of subsection iterations by the data actually present in the
decoded xref stream. Each entry consumes `sum(entry_sizes)` bytes (with the
`W[i]==0` default columns consuming 0), so the real entry count is at most
`len(stream_data) / max(1, sum(w for w in entry_sizes if w > 0))`.

```diff
--- a/pypdf/_reader.py
+++ b/pypdf/_reader.py
@@ def _read_pdf15_xref_stream(
         stream_data = BytesIO(xrefstream.get_data())
+        row_width = sum(w for w in entry_sizes if w > 0)
+        max_entries = len(stream_data.getbuffer()) // row_width if row_width else 0

         def get_entry(i: int) -> Union[int, tuple[int, ...]]:
@@ def used_before(
         # Iterate through each subsection
-        self._read_xref_subsections(idx_pairs, get_entry, used_before)
+        if self.strict and sum(s for _, s in self._pairs(idx_pairs)) > max_entries:
+            raise PdfReadError("XRef stream /Index exceeds available data")
+        idx_pairs = _clamp_idx_pairs(idx_pairs, max_entries)
+        self._read_xref_subsections(idx_pairs, get_entry, used_before)
         return xrefstream
```

where `_clamp_idx_pairs` reduces the subsection sizes so their total never
exceeds `max_entries`. (A simpler variant: break out of the `range(start,
start + size)` loop in `_read_xref_subsections` once `stream_data` is
exhausted.)

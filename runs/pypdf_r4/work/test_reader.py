import io, time, re
from hypothesis import given, settings, strategies as st, HealthCheck
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError, PdfStreamError

def base_pdf(n=1):
    w = PdfWriter()
    for _ in range(n):
        w.add_blank_page(100, 100)
    b = io.BytesIO(); w.write(b); return b.getvalue()

BASE = base_pdf()

def build(objs, trailer, xref_ok=True):
    out = b"%PDF-1.7\n"
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out)); out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offs:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n" + trailer + b"\nstartxref\n%d\n%%%%EOF\n" % xref
    return out

# Property 1: a missing/invalid /Root should be detected in time not proportional to an
# attacker-chosen /Size (PdfReadError "Cannot find Root object in pdf" is the documented result).
@settings(max_examples=20, deadline=None)
@given(st.integers(min_value=10**5, max_value=10**7))
def test_missing_root_bounded_time(size):
    data = build([b"<< /Type /Pages /Kids [] /Count 0 >>"], b"<< /Size %d >>" % size)
    r = PdfReader(io.BytesIO(data))
    t = time.perf_counter()
    try:
        len(r.pages)
    except PdfReadError:
        pass
    assert time.perf_counter() - t < 2.0, f"took {time.perf_counter()-t:.1f}s for /Size {size}"

# Property 2: parsing mutated PDFs raises only PdfReadError-family errors, not arbitrary crashes
@settings(max_examples=1000, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.data())
def test_mutated_pdf_no_crash(data):
    b = bytearray(BASE)
    for _ in range(data.draw(st.integers(1, 4))):
        i = data.draw(st.integers(0, len(b) - 1))
        b[i] = data.draw(st.integers(0, 255))
    try:
        r = PdfReader(io.BytesIO(bytes(b)))
        for p in r.pages:
            p.mediabox
    except (PdfReadError, PdfStreamError):
        pass

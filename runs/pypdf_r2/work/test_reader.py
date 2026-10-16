import io, time
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError, PdfStreamError
from pypdf.generic import NameObject, TextStringObject


def build_pdf(objs, trailer, xref_stream=False):
    """objs: list of bytes bodies for objects 1..n. trailer: bytes inner dict."""
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n" % (len(objs) + 1))
    out.write(b"0000000000 65535 f \n")
    for o in offsets:
        out.write(b"%010d 00000 n \n" % o)
    out.write(b"trailer\n<< " + trailer + b" >>\nstartxref\n%d\n%%%%EOF\n" % xref)
    return out.getvalue()


# Property 1: round trip of writer -> reader (metadata and page count)
@settings(max_examples=100, deadline=None)
@given(n_pages=st.integers(0, 10),
       meta=st.dictionaries(st.sampled_from(["/Title", "/Author", "/Subject", "/Keywords", "/Foo"]),
                            st.text(), max_size=5))
def test_roundtrip(n_pages, meta):
    w = PdfWriter()
    for _ in range(n_pages):
        w.add_blank_page(100, 100)
    w.add_metadata(meta)
    b = io.BytesIO(); w.write(b)
    r = PdfReader(io.BytesIO(b.getvalue()))
    assert len(r.pages) == n_pages
    for k, v in meta.items():
        assert r.metadata[k] == v


# Property 2: parsing a small malformed file should be fast (no DoS):
# trailer missing /Root but with an arbitrary /Size value.
@settings(max_examples=30, deadline=None, suppress_health_check=list(HealthCheck))
@given(size=st.integers(0, 10**7))
def test_missing_root_large_size_runtime(size):
    data = build_pdf([b"<< /Type /Pages /Kids [] /Count 0 >>"], b"/Size %d" % size)
    t = time.perf_counter()
    try:
        r = PdfReader(io.BytesIO(data))
        len(r.pages)
    except (PdfReadError, PdfStreamError):
        pass
    el = time.perf_counter() - t
    assert el < 2.0, f"{len(data)}-byte file took {el:.1f}s with /Size {size}"


# Property 3: xref stream with huge /Index and tiny data should be fast
@settings(max_examples=30, deadline=None, suppress_health_check=list(HealthCheck))
@given(size=st.integers(0, 10**8))
def test_xref_stream_index_runtime(size):
    out = io.BytesIO()
    out.write(b"%PDF-1.5\n")
    o1 = out.tell()
    out.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    o2 = out.tell()
    out.write(b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n")
    x = out.tell()
    out.write(b"3 0 obj\n<< /Type /XRef /Size 4 /Root 1 0 R /W [1 4 1] /Index [0 %d] /Length 0 >>\nstream\n\nendstream\nendobj\n" % size)
    out.write(b"startxref\n%d\n%%%%EOF\n" % x)
    t = time.perf_counter()
    try:
        PdfReader(io.BytesIO(out.getvalue()))
    except Exception:
        pass
    el = time.perf_counter() - t
    assert el < 2.0, f"took {el:.1f}s with /Index size {size}"

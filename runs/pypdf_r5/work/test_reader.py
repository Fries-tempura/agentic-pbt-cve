import io, time, zlib, struct
from hypothesis import given, settings, strategies as st, HealthCheck
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PyPdfError


def build_xref_stream_pdf(size, index=None, w=(1, 2, 1), extra_entries=True):
    """Build a minimal PDF 1.5 with a cross-reference stream."""
    out = io.BytesIO()
    out.write(b"%PDF-1.5\n")
    offs = {}
    offs[1] = out.tell()
    out.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    offs[2] = out.tell()
    out.write(b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n")
    xref_off = out.tell()
    rows = b""
    if extra_entries:
        rows += bytes([0]) + (0).to_bytes(w[1], "big") + bytes([255])[: w[2]]
        for i in (1, 2):
            rows += bytes([1]) + offs[i].to_bytes(w[1], "big") + (0).to_bytes(w[2], "big")
        rows += bytes([1]) + xref_off.to_bytes(w[1], "big") + (0).to_bytes(w[2], "big")
    data = zlib.compress(rows)
    idx = b"" if index is None else b"/Index [" + b" ".join(str(i).encode() for i in index) + b"] "
    out.write(b"3 0 obj\n<< /Type /XRef /Size %d %s/W [%d %d %d] /Root 1 0 R /Filter /FlateDecode /Length %d >>\nstream\n"
              % (size, idx, w[0], w[1], w[2], len(data)))
    out.write(data)
    out.write(b"\nendstream\nendobj\nstartxref\n%d\n%%%%EOF\n" % xref_off)
    return out.getvalue()


def test_valid_xref_stream():
    r = PdfReader(io.BytesIO(build_xref_stream_pdf(4)))
    assert len(r.pages) == 0
    assert r.root_object["/Type"] == "/Catalog"


@settings(max_examples=30, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.integers(min_value=4, max_value=2**40))
def test_xref_stream_size_terminates_quickly(size):
    data = build_xref_stream_pdf(size)
    t = time.time()
    import signal
    def h(*a): raise TimeoutError(f"/Size {size}: still parsing after 5s")
    signal.signal(signal.SIGALRM, h); signal.alarm(5)
    try:
        r = PdfReader(io.BytesIO(data))
        len(r.pages)
    except PyPdfError:
        pass
    finally:
        signal.alarm(0)
    assert time.time() - t < 5, f"took {time.time()-t:.1f}s for /Size {size}"


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=1, max_value=50),
       st.dictionaries(st.sampled_from(["/Title", "/Author", "/Subject", "/Producer"]),
                       st.text(st.characters(blacklist_categories=("Cs",)), max_size=30)),
       st.booleans())
def test_writer_reader_roundtrip(n, meta, compress):
    w = PdfWriter()
    for i in range(n):
        w.add_blank_page(width=100 + i, height=200)
    if meta:
        w.add_metadata(meta)
    if compress:
        for p in w.pages:
            p.compress_content_streams()
    buf = io.BytesIO()
    w.write(buf)
    r = PdfReader(io.BytesIO(buf.getvalue()))
    assert len(r.pages) == n
    for i, p in enumerate(r.pages):
        assert float(p.mediabox.width) == 100 + i
    for k, v in meta.items():
        assert r.metadata[k] == v


@settings(max_examples=300, deadline=None)
@given(st.data())
def test_mutated_pdf_no_unexpected_exceptions(data):
    w = PdfWriter()
    for _ in range(2):
        w.add_blank_page(100, 100)
    buf = io.BytesIO(); w.write(buf)
    b = bytearray(buf.getvalue())
    for _ in range(data.draw(st.integers(1, 5))):
        pos = data.draw(st.integers(0, len(b) - 1))
        b[pos] = data.draw(st.integers(0, 255))
    t = time.time()
    try:
        r = PdfReader(io.BytesIO(bytes(b)))
        len(r.pages)
    except PyPdfError:
        pass
    assert time.time() - t < 5

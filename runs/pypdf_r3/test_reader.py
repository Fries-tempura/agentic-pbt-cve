import io, time, logging
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PyPdfError
from pdfgen import build_pdf

logging.disable(logging.CRITICAL)

CATALOG = b"<< /Type /Catalog /Pages 2 0 R >>"
PAGES = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
PAGE = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] >>"


@given(st.integers(1, 2000), st.integers(1, 2000), st.sampled_from([b" \n", b"\r\n", b" \r"]))
def test_valid_pdf_parses(w, h, eol):
    data = build_pdf([CATALOG, PAGES, PAGE % (w, h)], eol=eol)
    r = PdfReader(io.BytesIO(data))
    assert len(r.pages) == 1
    assert r.pages[0].mediabox.width == w and r.pages[0].mediabox.height == h


@given(st.lists(st.tuples(st.integers(1, 3000), st.integers(1, 3000)), min_size=1, max_size=10),
       st.dictionaries(st.sampled_from(["/Title", "/Author", "/Subject"]), st.text(min_size=0, max_size=30)))
@settings(max_examples=100, deadline=None)
def test_writer_reader_roundtrip(sizes, meta):
    w = PdfWriter()
    for a, b in sizes:
        w.add_blank_page(a, b)
    if meta:
        w.add_metadata(meta)
    buf = io.BytesIO()
    w.write(buf)
    r = PdfReader(io.BytesIO(buf.getvalue()))
    assert [(p.mediabox.width, p.mediabox.height) for p in r.pages] == list(sizes)
    for k, v in meta.items():
        assert r.metadata[k] == v


# Robustness: a PDF whose /Root is missing must fail/succeed quickly regardless of /Size
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
    assert time.time() - t < 2.0, f"root_object took {time.time()-t:.1f}s for /Size {size}"


# Mutation fuzz: random byte corruption should only raise pypdf errors
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
    t = time.time()
    try:
        r = PdfReader(io.BytesIO(bytes(pdf)))
        for p in r.pages:
            p.mediabox
    except (PyPdfError, ValueError, KeyError, TypeError, AttributeError, IndexError, AssertionError, RecursionError) as e:
        if isinstance(e, PyPdfError):
            return
        raise
    finally:
        assert time.time() - t < 5

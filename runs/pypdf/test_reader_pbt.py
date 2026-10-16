import time
from io import BytesIO

from hypothesis import given, settings, strategies as st

from pypdf import PdfReader, PdfWriter


def make_xref_stream_pdf(size: int, index=None) -> bytes:
    """Build a small, well-formed PDF 1.5 file using a cross-reference stream.

    `size` is written as the xref stream's /Size, `index` (optional) as /Index.
    The actual stream data only contains entries for the real objects.
    """
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
    for off in offsets:
        rows.append(bytes([1]) + off.to_bytes(2, "big") + bytes([0]))
    rows.append(bytes([1]) + xref_off.to_bytes(2, "big") + bytes([0]))
    data = b"".join(rows)
    idx = b""
    if index is not None:
        idx = b" /Index [" + b" ".join(b"%d" % v for v in index) + b"]"
    out += (
        b"5 0 obj\n<< /Type /XRef /Size %d /W [1 2 1] /Root 1 0 R /Length %d%s >>\nstream\n"
        % (size, len(data), idx)
    )
    out += data + b"\nendstream\nendobj\n"
    out += b"startxref\n%d\n%%%%EOF\n" % xref_off
    return bytes(out)


def test_sanity_valid_pdf():
    r = PdfReader(BytesIO(make_xref_stream_pdf(6)))
    assert len(r.pages) == 1


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=6, max_value=2**31 - 1))
def test_xref_stream_size_does_not_blow_up(size):
    # Parsing a ~400 byte PDF should take time proportional to the file,
    # not to the (attacker controlled) /Size value.
    pdf = make_xref_stream_pdf(size)
    t = time.perf_counter()
    r = PdfReader(BytesIO(pdf))
    elapsed = time.perf_counter() - t
    assert len(r.pages) == 1
    assert elapsed < 2.0, (size, elapsed)


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=6, max_value=2**31 - 1))
def test_xref_stream_index_does_not_blow_up(count):
    pdf = make_xref_stream_pdf(6, index=[0, count])
    t = time.perf_counter()
    PdfReader(BytesIO(pdf))
    elapsed = time.perf_counter() - t
    assert elapsed < 2.0, (count, elapsed)


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=1, max_value=20), st.binary(max_size=30))
def test_roundtrip_writer_reader(n_pages, title):
    w = PdfWriter()
    for _ in range(n_pages):
        w.add_blank_page(10, 10)
    w.add_metadata({"/Title": title.decode("latin-1")})
    buf = BytesIO()
    w.write(buf)
    r = PdfReader(BytesIO(buf.getvalue()))
    assert len(r.pages) == n_pages
    assert r.metadata.title == title.decode("latin-1")

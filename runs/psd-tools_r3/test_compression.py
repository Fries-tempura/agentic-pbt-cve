import pytest
from hypothesis import given, settings, strategies as st, assume
from psd_tools.compression import compress, decompress, rle as py_rle
from psd_tools.compression import _rle as cy_rle
from psd_tools.constants import Compression


@st.composite
def image(draw, depths=(8, 16, 32)):
    depth = draw(st.sampled_from(depths))
    w = draw(st.integers(1, 20))
    h = draw(st.integers(1, 8))
    n = w * h * depth // 8
    data = draw(st.one_of(
        st.binary(min_size=n, max_size=n),
        st.lists(st.sampled_from([0, 1, 255]), min_size=n, max_size=n).map(bytes),
    ))
    return data, w, h, depth


@settings(max_examples=500)
@given(image(), st.sampled_from(list(Compression)), st.sampled_from([1, 2]))
def test_roundtrip(img, comp, version):
    data, w, h, depth = img
    c = compress(data, comp, w, h, depth, version)
    assert decompress(c, comp, w, h, depth, version) == data


runs = st.lists(st.tuples(st.integers(0, 255), st.integers(1, 300)), max_size=10).map(
    lambda rs: b"".join(bytes([b]) * n for b, n in rs))


@settings(max_examples=1000)
@given(st.one_of(st.binary(), runs))
def test_rle_roundtrip_and_equivalence(data):
    e1 = py_rle.encode(data)
    e2 = cy_rle.encode(data)
    assert bytes(e1) == bytes(e2)
    assume(len(data) > 0)
    assert py_rle.decode(e1, len(data)) == data
    assert cy_rle.decode(e1, len(data)) == data


def _call(f, *a):
    try:
        return ("ok", bytes(f(*a)))
    except Exception as e:
        return ("err", type(e).__name__)


@settings(max_examples=2000)
@given(st.binary(max_size=40), st.integers(0, 60))
def test_rle_decode_equivalence(data, size):
    assert _call(py_rle.decode, data, size) == _call(cy_rle.decode, data, size)


@st.composite
def bitmap(draw):
    w = draw(st.integers(1, 40))
    h = draw(st.integers(1, 6))
    n = ((w + 7) // 8) * h  # PSD bitmap rows are padded to whole bytes
    return draw(st.binary(min_size=n, max_size=n)), w, h


@settings(max_examples=500)
@given(bitmap(), st.sampled_from([Compression.RLE, Compression.ZIP]), st.sampled_from([1, 2]))
def test_bitmap_roundtrip(img, comp, version):
    data, w, h = img
    c = compress(data, comp, w, h, 1, version)
    assert decompress(c, comp, w, h, 1, version) == data

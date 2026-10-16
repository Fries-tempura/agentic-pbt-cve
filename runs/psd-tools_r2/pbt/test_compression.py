from hypothesis import given, settings, strategies as st, assume
import pytest
from psd_tools.compression import compress, decompress, encode_prediction, decode_prediction
from psd_tools.compression import rle as py_rle, _rle as c_rle
from psd_tools.constants import Compression

dims = st.tuples(st.integers(1, 12), st.integers(1, 12), st.sampled_from([8, 16, 32]))

@st.composite
def image(draw):
    w, h, d = draw(dims)
    n = w * h * d // 8
    data = draw(st.binary(min_size=n, max_size=n) | st.lists(st.sampled_from([0, 1, 255]), min_size=n, max_size=n).map(bytes))
    return data, w, h, d

@settings(max_examples=500)
@given(image(), st.sampled_from(list(Compression)), st.sampled_from([1, 2]))
def test_roundtrip(img, comp, version):
    data, w, h, d = img
    enc = compress(data, comp, w, h, d, version)
    assert decompress(enc, comp, w, h, d, version) == data

@settings(max_examples=2000)
@given(st.binary(max_size=600) | st.lists(st.sampled_from([0, 1]), max_size=600).map(bytes))
def test_rle_roundtrip_and_impls_agree(data):
    e1 = bytes(py_rle.encode(data)); e2 = bytes(c_rle.encode(data))
    assert e1 == e2
    assert py_rle.decode(e1, len(data)) == data
    assert c_rle.decode(e1, len(data)) == data

@settings(max_examples=3000)
@given(st.binary(max_size=40), st.integers(0, 60))
def test_rle_decode_impls_agree(data, size):
    def run(f):
        try:
            return ("ok", bytes(f(data, size)))
        except (ValueError, IndexError):
            return ("err", None)
    r1, r2 = run(py_rle.decode), run(c_rle.decode)
    assert r1 == r2
    if r1[0] == "ok" and size:
        assert len(r1[1]) == size

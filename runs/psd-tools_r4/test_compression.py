import zlib
import pytest
from hypothesis import given, settings, strategies as st, assume
from psd_tools.compression import compress, decompress, encode_rle, decode_rle, rle_impl
from psd_tools.compression import rle as py_rle
from psd_tools.compression import _rle as cy_rle
from psd_tools.constants import Compression

runs = st.lists(st.tuples(st.integers(0, 255), st.integers(1, 300)), max_size=20).map(
    lambda l: b"".join(bytes([v]) * n for v, n in l))
data_st = st.one_of(st.binary(max_size=1000), runs)

@settings(max_examples=1000)
@given(data_st)
def test_rle_roundtrip_py(data):
    assert py_rle.decode(py_rle.encode(data), len(data)) == data

@settings(max_examples=1000)
@given(data_st)
def test_rle_roundtrip_cy(data):
    assert cy_rle.decode(cy_rle.encode(data), len(data)) == data

@settings(max_examples=1000)
@given(data_st)
def test_rle_impls_agree_encode(data):
    assert bytes(py_rle.encode(data)) == bytes(cy_rle.encode(data))

@settings(max_examples=2000)
@given(st.binary(max_size=200), st.integers(0, 300))
def test_rle_impls_agree_decode(data, size):
    def run(f):
        try:
            return ("ok", bytes(f(data, size)))
        except ValueError:
            return ("err", None)
    p, c = run(py_rle.decode), run(cy_rle.decode)
    assert p == c
    if p[0] == "ok" and size:
        assert len(p[1]) == size

@st.composite
def image(draw):
    depth = draw(st.sampled_from([8, 16, 32]))
    w = draw(st.integers(1, 20)); h = draw(st.integers(1, 20))
    n = w * h * depth // 8
    data = draw(st.one_of(st.binary(min_size=n, max_size=n),
                          st.integers(0, 255).map(lambda b: bytes([b]) * n)))
    return data, w, h, depth

@settings(max_examples=500)
@given(image(), st.sampled_from(list(Compression)), st.sampled_from([1, 2]))
def test_compress_roundtrip(img, comp, version):
    data, w, h, depth = img
    c = compress(data, comp, w, h, depth, version)
    assert decompress(c, comp, w, h, depth, version) == data

@settings(max_examples=300)
@given(st.integers(1, 64), st.integers(1, 20), st.sampled_from([1, 2]), st.data())
def test_compress_roundtrip_depth1(w, h, version, d):
    rowbytes = (w + 7) // 8
    data = d.draw(st.binary(min_size=rowbytes * h, max_size=rowbytes * h))
    c = compress(data, Compression.RLE, w, h, 1, version)
    assert decompress(c, Compression.RLE, w, h, 1, version) == data

from hypothesis import given, settings, strategies as st
from psd_tools.compression import compress, decompress, rle as py_rle
from psd_tools.compression import _rle as c_rle
from psd_tools.constants import Compression


def runs_to_bytes(r):
    return b"".join(bytes([v]) * c for v, c in r)


runs = st.lists(st.tuples(st.integers(0, 255), st.integers(1, 300))).map(runs_to_bytes)
anydata = st.one_of(st.binary(), runs)


@st.composite
def image(draw):
    depth = draw(st.sampled_from([8, 16, 32]))
    w = draw(st.integers(1, 40))
    h = draw(st.integers(1, 10))
    n = w * h * depth // 8
    seed = draw(st.one_of(st.binary(min_size=1), runs.filter(len)))
    data = (seed * (n // len(seed) + 1))[:n]
    return data, w, h, depth


@settings(max_examples=500)
@given(image(), st.sampled_from(list(Compression)), st.sampled_from([1, 2]))
def test_roundtrip(img, comp, version):
    data, w, h, depth = img
    c = compress(data, comp, w, h, depth, version)
    assert decompress(c, comp, w, h, depth, version) == data


@settings(max_examples=1000)
@given(anydata)
def test_rle_roundtrip_both(data):
    for enc in (py_rle.encode, c_rle.encode):
        e = bytes(enc(data))
        for dec in (py_rle.decode, c_rle.decode):
            assert bytes(dec(e, len(data))) == data
    assert bytes(py_rle.encode(data)) == bytes(c_rle.encode(data))


@settings(max_examples=3000)
@given(st.binary(), st.integers(0, 600))
def test_decode_equivalence(data, size):
    res = []
    for dec in (py_rle.decode, c_rle.decode):
        try:
            res.append(("ok", bytes(dec(data, size))))
        except ValueError:
            res.append(("err", None))
    assert res[0] == res[1]


@settings(max_examples=2000)
@given(st.binary(max_size=200), st.integers(1, 20), st.integers(1, 10),
       st.sampled_from([8, 16, 32]), st.sampled_from([1, 2]))
def test_decompress_rle_garbage(data, w, h, depth, version):
    try:
        out = decompress(data, Compression.RLE, w, h, depth, version)
    except ValueError:
        return
    assert len(out) == w * h * depth // 8

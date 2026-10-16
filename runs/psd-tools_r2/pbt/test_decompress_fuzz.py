import zlib
from hypothesis import given, settings, strategies as st
from psd_tools.compression import decompress
from psd_tools.constants import Compression

@settings(max_examples=2000)
@given(st.binary(max_size=64), st.integers(1, 8), st.integers(1, 8), st.sampled_from([8, 16, 32]),
       st.sampled_from([Compression.RLE, Compression.ZIP, Compression.ZIP_WITH_PREDICTION]), st.sampled_from([1, 2]))
def test_decompress_result_or_valueerror(payload, w, h, d, comp, v):
    if comp != Compression.RLE:
        payload = zlib.compress(payload)
    try:
        out = decompress(payload, comp, w, h, d, v)
    except (ValueError, zlib.error):
        return
    assert len(out) == w * h * d // 8

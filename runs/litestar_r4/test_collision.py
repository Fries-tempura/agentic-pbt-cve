import asyncio, tempfile
from pathlib import Path
from hypothesis import given, settings, assume, strategies as st
from litestar.stores.file import FileStore

ascii_keys = st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=20)

@st.composite
def key_pairs(draw):
    k1 = draw(ascii_keys)
    k2 = "".join(c if c.isalnum() else str(ord(c)) for c in k1)
    assume(k1 != k2)
    return k1, k2

@settings(max_examples=200, deadline=None)
@given(key_pairs(), st.binary(min_size=1), st.binary(min_size=1))
def test_distinct_keys_do_not_overwrite_each_other(pair, v1, v2):
    k1, k2 = pair
    assume(v1 != v2)
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        async def go():
            await store.set(k1, v1)
            await store.set(k2, v2)
            return await store.get(k1)
        assert asyncio.run(go()) == v1

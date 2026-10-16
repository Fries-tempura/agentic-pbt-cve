import asyncio, tempfile
from pathlib import Path
from hypothesis import given, settings, assume, strategies as st
from litestar.stores.file import FileStore

keys = st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=20)

def run(coro):
    return asyncio.run(coro)

@settings(max_examples=2000)
@given(keys, keys)
def test_distinct_keys_isolated(k1, k2):
    assume(k1 != k2)
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(k1, b"v1")
            await s.set(k2, b"v2")
            return await s.get(k1)
    assert run(go()) == b"v1"

@settings(max_examples=200)
@given(st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=300))
def test_set_then_get(key):
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(key, b"v")
            return await s.get(key)
    assert run(go()) == b"v"

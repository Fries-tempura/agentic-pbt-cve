import asyncio, tempfile
from pathlib import Path
from hypothesis import given, settings, strategies as st
from litestar.stores.file import FileStore

alnum = st.text(st.characters(categories=["Ll", "Lu", "Nd"], max_codepoint=127), max_size=10)
special = st.characters(min_codepoint=32, max_codepoint=126).filter(lambda c: not c.isalnum())

def run(coro):
    return asyncio.run(coro)

@given(alnum, special, alnum)
def test_distinct_keys_isolated(prefix, c, suffix):
    k1 = prefix + c + suffix
    k2 = prefix + str(ord(c)) + suffix
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(k1, b"v1")
            await s.set(k2, b"v2")
            return await s.get(k1)
    assert run(go()) == b"v1"

@settings(max_examples=50)
@given(st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=128, max_size=400))
def test_set_then_get_long_key(key):
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(key, b"v")
            return await s.get(key)
    assert run(go()) == b"v"

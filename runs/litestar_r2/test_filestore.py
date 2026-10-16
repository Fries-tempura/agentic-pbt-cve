import asyncio, tempfile
from pathlib import Path
from hypothesis import given, settings, assume, strategies as st
from litestar.stores.file import FileStore, _safe_file_name

keys = st.text(min_size=1, max_size=50)

def run(coro):
    return asyncio.run(coro)

@settings(max_examples=500)
@given(keys, st.binary())
def test_set_get_roundtrip(key, value):
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(key, value)
            return await s.get(key)
    assert run(go()) == value

@settings(max_examples=1000)
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

@settings(max_examples=1000)
@given(keys, keys)
def test_delete_only_removes_own_key(k1, k2):
    assume(k1 != k2)
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(k1, b"v1")
            await s.delete(k2)
            return await s.exists(k1)
    assert run(go())

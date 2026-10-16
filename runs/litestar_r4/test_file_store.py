import asyncio, tempfile
from pathlib import Path
from hypothesis import given, settings, assume, strategies as st
from litestar.stores.file import FileStore, _safe_file_name

keys = st.text(min_size=1, max_size=20)

def run(coro):
    return asyncio.run(coro)

@settings(max_examples=300, deadline=None)
@given(keys, st.binary())
def test_set_get_roundtrip(key, value):
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d) / "s")
        async def go():
            await store.set(key, value)
            return await store.get(key)
        assert run(go()) == value

@settings(max_examples=1000, deadline=None)
@given(keys, keys)
def test_distinct_keys_distinct_files(k1, k2):
    assume(k1 != k2)
    assert _safe_file_name(k1) != _safe_file_name(k2)

@settings(max_examples=300, deadline=None)
@given(keys, keys, st.binary(), st.binary())
def test_distinct_keys_independent(k1, k2, v1, v2):
    assume(k1 != k2)
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d) / "s")
        async def go():
            await store.set(k1, v1)
            await store.set(k2, v2)
            return await store.get(k1), await store.get(k2)
        assert run(go()) == (v1, v2)

@settings(max_examples=200, deadline=None)
@given(keys, st.binary())
def test_delete_then_absent(key, value):
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d) / "s")
        async def go():
            await store.set(key, value)
            await store.delete(key)
            return await store.get(key), await store.exists(key)
        assert run(go()) == (None, False)

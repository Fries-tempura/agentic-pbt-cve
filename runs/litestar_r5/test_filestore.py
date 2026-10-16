import asyncio, tempfile
from pathlib import Path
from hypothesis import given, settings, assume, strategies as st
from litestar.stores.file import FileStore, _safe_file_name

def run(coro):
    return asyncio.run(coro)

keys = st.text(min_size=1, max_size=30)

@settings(max_examples=500)
@given(keys, keys)
def test_distinct_keys_distinct_files(k1, k2):
    assume(k1 != k2)
    assert _safe_file_name(k1) != _safe_file_name(k2)

@settings(max_examples=200, deadline=None)
@given(keys, keys, st.binary(), st.binary())
def test_set_get_independent(k1, k2, v1, v2):
    assume(k1 != k2)
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(k1, v1)
            await s.set(k2, v2)
            return await s.get(k1)
    assert run(go()) == v1

@settings(max_examples=200, deadline=None)
@given(keys, st.binary())
def test_roundtrip(k, v):
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(k, v)
            return await s.get(k)
    assert run(go()) == v

@settings(max_examples=1000)
@given(st.lists(st.sampled_from(list("0123456789-_.:/ ab")), min_size=1, max_size=6),
       st.lists(st.sampled_from(list("0123456789-_.:/ ab")), min_size=1, max_size=6))
def test_distinct_keys_distinct_files_ascii(a, b):
    k1, k2 = "".join(a), "".join(b)
    assume(k1 != k2)
    assert _safe_file_name(k1) != _safe_file_name(k2)

@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=1, max_value=600))
def test_long_key_get_no_crash(n):
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set("k" * n, b"v")
            return await s.get("k" * n)
    assert run(go()) == b"v"

@settings(max_examples=200, deadline=None)
@given(st.text(alphabet=st.characters(codec="ascii", categories=["P","S","Zs"]), min_size=1, max_size=10))
def test_encoded_key_does_not_alias(k1):
    k2 = _safe_file_name(k1)
    assume(k1 != k2)
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(k1, b"secret")
            return await s.get(k2)
    assert run(go()) is None

import asyncio
import tempfile
from pathlib import Path

from hypothesis import given, settings, assume, strategies as st

from litestar.stores.file import FileStore

keys = st.text(min_size=1)
vals = st.binary()


def run(coro_fn):
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d) / "s")
        return asyncio.run(coro_fn(store))


@settings(max_examples=300, deadline=None)
@given(keys, vals)
def test_round_trip(k, v):
    """CLAIM-1: after set(k, v), get(k) == v."""
    async def go(s):
        await s.set(k, v)
        return await s.get(k)
    assert run(go) == v


@settings(max_examples=1000, deadline=None)
@given(keys, keys, vals, vals)
def test_distinct_keys_independent(k1, k2, v1, v2):
    """CLAIM-2: distinct keys hold independent values."""
    assume(k1 != k2 and v1 != v2)
    async def go(s):
        await s.set(k1, v1)
        await s.set(k2, v2)
        return await s.get(k1), await s.get(k2)
    assert run(go) == (v1, v2)


@settings(max_examples=1000, deadline=None)
@given(keys, keys, vals)
def test_delete_other_key(k1, k2, v1):
    """CLAIM-3: deleting k2 does not affect k1."""
    assume(k1 != k2)
    async def go(s):
        await s.set(k1, v1)
        await s.delete(k2)
        return await s.get(k1)
    assert run(go) == v1

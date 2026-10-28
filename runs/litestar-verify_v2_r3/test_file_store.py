import asyncio
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st, HealthCheck

from litestar.stores.file import FileStore

S = settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck))
keys = st.text(alphabet="a45-ﬁf ", min_size=1, max_size=3)


def run(coro_fn):
    with tempfile.TemporaryDirectory() as d:
        return asyncio.run(coro_fn(FileStore(Path(d) / "s")))


@S
@given(ks=st.lists(keys, unique=True, min_size=2, max_size=8))
def test_distinct_keys_isolated(ks):
    """CLAIM-1: distinct keys keep distinct values."""
    async def body(store):
        for i, k in enumerate(ks):
            await store.set(k, str(i))
        return [await store.get(k) for k in ks]
    got = run(body)
    assert got == [str(i).encode() for i in range(len(ks))], list(zip(ks, got))


@S
@given(k=st.text(min_size=1, max_size=300), v=st.binary(max_size=20))
def test_set_get_roundtrip(k, v):
    """CLAIM-2/CLAIM-3: set then get returns the value; no crash."""
    async def body(store):
        await store.set(k, v)
        return await store.get(k)
    assert run(body) == v


@S
@given(k=st.text(min_size=1, max_size=20))
def test_expires_in_none(k):
    """CLAIM-4: no expiry set -> expires_in is None."""
    async def body(store):
        await store.set(k, b"x")
        return await store.expires_in(k)
    assert run(body) is None


@S
@given(ns=st.text(alphabet="abc01", min_size=1, max_size=3), k=st.text(alphabet="abc01", min_size=1, max_size=3))
def test_namespace_isolated(ns, k):
    """CLAIM-5: child namespace ops don't affect parent keys."""
    async def body(store):
        child = store.with_namespace(ns)
        await store.set("seed", b"s")
        await child.set("x", b"child")
        await store.set(k, b"parent")
        return await store.get(k)
    assert run(body) == b"parent"

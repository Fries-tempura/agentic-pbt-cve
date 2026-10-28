import asyncio
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st

from litestar.stores.file import FileStore

# Alphabet from the mechanism: alnum pass through, everything else becomes str(ord(c));
# digits can forge those encodings; NFKD-affected chars (ligature, superscript, accent).
KEY_ALPHA = "ab0123456789-_.!:/ ﬁ²é"
keys = st.text(alphabet=KEY_ALPHA, min_size=1, max_size=6)


def run(coro):
    return asyncio.run(coro)


@settings(max_examples=300, deadline=None)
@given(ks=st.lists(keys, unique=True, min_size=2, max_size=8))
def test_distinct_keys_do_not_collide(ks):
    """CLAIM-1: distinct keys keep distinct values."""
    async def body():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            for i, k in enumerate(ks):
                await store.set(k, str(i).encode())
            return {k: await store.get(k) for k in ks}
    got = run(body())
    assert got == {k: str(i).encode() for i, k in enumerate(ks)}


@settings(max_examples=200, deadline=None)
@given(k=st.text(min_size=1), v=st.binary())
def test_round_trip(k, v):
    """CLAIM-2: set then get returns the value."""
    async def body():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            await store.set(k, v)
            return await store.get(k)
    assert run(body()) == v


@settings(max_examples=200, deadline=None)
@given(k=st.text())
def test_no_crash(k):
    """CLAIM-3: get/exists/delete never raise for str keys."""
    async def body():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            await store.set("other", b"x")
            await store.get(k)
            await store.exists(k)
            await store.delete(k)
    run(body())


@given(k=keys)
@settings(max_examples=20, deadline=None)
def test_expires_in_none(k):
    """CLAIM-4: no expiry -> expires_in returns None."""
    async def body():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            await store.set(k, b"v")
            return await store.expires_in(k)
    assert run(body()) is None


@settings(max_examples=100, deadline=None)
@given(ns=st.text(alphabet="ab12", min_size=1, max_size=3), k=keys)
def test_namespace_isolation(ns, k):
    """CLAIM-5: values in a child namespace are not visible from the parent."""
    async def body():
        with tempfile.TemporaryDirectory() as d:
            parent = FileStore(Path(d))
            child = parent.with_namespace(ns)
            await child.set(k, b"child")
            return await parent.get(ns), await parent.exists(ns)
    got, ex = run(body())
    assert got is None and ex is False


@settings(max_examples=300, deadline=None)
@given(ks=st.lists(st.text(alphabet="a3!ﬁf", min_size=1, max_size=4), unique=True, min_size=2, max_size=8))
def test_distinct_keys_do_not_collide_mech(ks):
    """CLAIM-1: distinct keys keep distinct values (mechanism-targeted alphabet)."""
    test_distinct_keys_do_not_collide.hypothesis.inner_test(ks)


@settings(max_examples=50, deadline=None)
@given(k=st.text(alphabet="ab/?=&", min_size=100, max_size=400))
def test_long_key_round_trip(k):
    """CLAIM-2/CLAIM-3: long keys round-trip without raising."""
    test_round_trip.hypothesis.inner_test(k, b"v")

import asyncio
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st

from litestar.stores.file import FileStore

# Alphanumerics (kept as-is), digits (which also appear in ord() encodings),
# separators (replaced by ord), and NFKD-decomposing chars.
ALPHABET = "a0123456789-./_²ﬁfi"
keys = st.text(alphabet=ALPHABET, min_size=1, max_size=4)


def run(coro):
    return asyncio.run(coro)


@settings(max_examples=1000, deadline=None)
@given(ks=st.lists(keys, unique=True, min_size=2, max_size=12))
def test_distinct_keys_keep_values(ks):
    """CLAIM-1: distinct keys each keep their own value."""
    async def go():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            for i, k in enumerate(ks):
                await store.set(k, str(i).encode())
            return [await store.get(k) for k in ks]
    got = run(go())
    assert got == [str(i).encode() for i in range(len(ks))], list(zip(ks, got))


@settings(max_examples=1000, deadline=None)
@given(k1=keys, others=st.lists(keys, min_size=1, max_size=12))
def test_exists_only_set_key(k1, others):
    """CLAIM-2: only the set key exists."""
    others = [k for k in others if k != k1]
    async def go():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            await store.set(k1, b"v")
            return {k: await store.exists(k) for k in others}
    res = run(go())
    assert not any(res.values()), (k1, res)


@settings(max_examples=1000, deadline=None)
@given(k1=keys, others=st.lists(keys, min_size=1, max_size=12))
def test_delete_other_key_noop(k1, others):
    """CLAIM-3: deleting other keys does not remove k1's value."""
    others = [k for k in others if k != k1]
    async def go():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            await store.set(k1, b"v")
            for k in others:
                await store.delete(k)
            return await store.get(k1)
    assert run(go()) == b"v", (k1, others)


@settings(max_examples=200, deadline=None)
@given(k=st.text(max_size=300))
def test_round_trip_any_key(k):
    """CLAIM-4: set then get round-trips for any str key without raising."""
    async def go():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            await store.set(k, b"v")
            return await store.get(k)
    assert run(go()) == b"v"

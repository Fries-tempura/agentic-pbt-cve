import tempfile
from pathlib import Path

import anyio
from hypothesis import assume, given, settings, strategies as st

from litestar.stores.file import FileStore

keys = st.text(min_size=1, max_size=20)


def run(coro_fn):
    return anyio.run(coro_fn)


@settings(max_examples=500, deadline=None)
@given(keys, keys)
def test_distinct_keys_are_independent(k1, k2):
    assume(k1 != k2)

    async def main():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            await store.set(k1, b"one")
            await store.set(k2, b"two")
            return await store.get(k1), await store.get(k2)

    v1, v2 = run(main)
    assert v1 == b"one", (k1, k2, v1)
    assert v2 == b"two"


@settings(max_examples=200, deadline=None)
@given(st.text(min_size=1), st.binary())
def test_set_get_roundtrip(k, v):
    async def main():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            await store.set(k, v)
            return await store.get(k)

    assert run(main) == v


ascii_keys = st.text(st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=10)


@settings(max_examples=2000, deadline=None)
@given(ascii_keys, ascii_keys)
def test_distinct_ascii_keys_are_independent(k1, k2):
    assume(k1 != k2)

    async def main():
        with tempfile.TemporaryDirectory() as d:
            store = FileStore(Path(d))
            await store.set(k1, b"one")
            await store.set(k2, b"two")
            return await store.get(k1)

    assert run(main) == b"one", (k1, k2)

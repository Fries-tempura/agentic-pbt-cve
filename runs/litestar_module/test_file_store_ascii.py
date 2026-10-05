"""Property tests for litestar.stores.file.FileStore using plain ASCII keys.

Keys are restricted to printable ASCII -- the kind of key any real caller uses
(session ids, cache keys, URLs, emails, ...) -- so failures here are not
filesystem/platform artifacts.
"""

import string
import tempfile
from pathlib import Path

import anyio
from hypothesis import given, settings
from hypothesis import strategies as st

from litestar.stores.file import FileStore, _safe_file_name

ascii_keys = st.text(alphabet=string.printable[:94], min_size=1, max_size=12)
values = st.binary(min_size=1, max_size=32)


def make_store():
    return FileStore(Path(tempfile.mkdtemp()))


@settings(max_examples=2000)
@given(k1=ascii_keys, k2=ascii_keys)
def test_safe_file_name_injective(k1, k2):
    """The key -> filename mapping must not collide, or keys share storage."""
    if k1 == k2:
        return
    assert _safe_file_name(k1) != _safe_file_name(k2)


@settings(max_examples=1000)
@given(k1=ascii_keys, k2=ascii_keys, v1=values, v2=values)
def test_distinct_keys_are_isolated(k1, k2, v1, v2):
    """Writing k2 must not clobber the value stored under a different key k1."""
    if k1 == k2:
        return
    store = make_store()

    async def run():
        await store.set(k1, v1)
        await store.set(k2, v2)
        assert await store.get(k1) == v1

    anyio.run(run)


@settings(max_examples=1000)
@given(k1=ascii_keys, k2=ascii_keys)
def test_delete_does_not_affect_other_keys(k1, k2):
    """delete(k2) is documented to delete 'the value of key' -- only that key."""
    if k1 == k2:
        return
    store = make_store()

    async def run():
        await store.set(k1, b"payload")
        await store.delete(k2)
        assert await store.exists(k1) is True

    anyio.run(run)


@settings(max_examples=500)
@given(key=ascii_keys, value=values)
def test_set_get_round_trip(key, value):
    store = make_store()

    async def run():
        await store.set(key, value)
        assert await store.get(key) == value

    anyio.run(run)

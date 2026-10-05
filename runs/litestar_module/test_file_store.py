import tempfile
from pathlib import Path

import anyio
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from litestar.stores.file import FileStore, _safe_file_name

# keys: realistic cache/session-ish keys -- any text the user may pass
keys = st.text(min_size=1, max_size=20)
values = st.binary(max_size=64)


def make_store():
    tmpdir = tempfile.mkdtemp()
    return FileStore(Path(tmpdir))


@settings(max_examples=500, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(key=keys, value=values)
def test_set_get_round_trip(key, value):
    """Store docstring: get() returns 'The value associated with ``key``'."""
    store = make_store()

    async def run():
        await store.set(key, value)
        assert await store.get(key) == value

    anyio.run(run)


@settings(max_examples=1000)
@given(k1=keys, k2=keys, v1=values, v2=values)
def test_distinct_keys_are_isolated(k1, k2, v1, v2):
    """Distinct keys must map to distinct entries: writing k2 must not clobber k1."""
    if k1 == k2:
        return
    store = make_store()

    async def run():
        await store.set(k1, v1)
        await store.set(k2, v2)
        assert await store.get(k1) == v1
        assert await store.get(k2) == v2

    anyio.run(run)


@settings(max_examples=1000)
@given(k1=keys, k2=keys)
def test_delete_does_not_affect_other_keys(k1, k2):
    """delete(k2) must not remove k1's value when k1 != k2."""
    if k1 == k2:
        return
    store = make_store()

    async def run():
        await store.set(k1, b"payload")
        await store.delete(k2)
        assert await store.exists(k1) is True

    anyio.run(run)


@settings(max_examples=2000)
@given(k1=keys, k2=keys)
def test_safe_file_name_injective(k1, k2):
    """_safe_file_name is the key->filename mapping; it must not collide."""
    if k1 == k2:
        return
    assert _safe_file_name(k1) != _safe_file_name(k2)


@settings(max_examples=300)
@given(key=keys)
def test_exists_false_for_unset_key(key):
    store = make_store()

    async def run():
        assert await store.exists(key) is False

    anyio.run(run)

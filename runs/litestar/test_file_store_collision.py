"""Collision hunt for litestar.stores.file.FileStore key encoding.

Alphabet is narrowed to characters that genuinely show up in cache/session keys
(digits, letters, and the usual separators) so Hypothesis can actually explore
the collision space.
"""

import tempfile
from pathlib import Path

import anyio
from hypothesis import given, settings
from hypothesis import strategies as st

from litestar.stores.file import FileStore, _safe_file_name

ALPHABET = "0123456789ab-_/:."
keys = st.text(alphabet=ALPHABET, min_size=1, max_size=4)


def make_store():
    return FileStore(Path(tempfile.mkdtemp()))


@settings(max_examples=5000)
@given(k1=keys, k2=keys)
def test_safe_file_name_injective(k1, k2):
    if k1 == k2:
        return
    assert _safe_file_name(k1) != _safe_file_name(k2), (
        f"{k1!r} and {k2!r} both map to {_safe_file_name(k1)!r}"
    )


@settings(max_examples=2000)
@given(ks=st.lists(keys, unique=True, min_size=2, max_size=8))
def test_safe_file_name_injective_over_set(ks):
    """Distinct keys must produce distinct filenames."""
    encoded = [_safe_file_name(k) for k in ks]
    assert len(set(encoded)) == len(ks), f"collision among {ks!r} -> {encoded!r}"


@settings(max_examples=3000)
@given(k1=keys, k2=keys)
def test_distinct_keys_are_isolated(k1, k2):
    if k1 == k2:
        return
    store = make_store()

    async def run():
        await store.set(k1, b"value-one")
        await store.set(k2, b"value-two")
        assert await store.get(k1) == b"value-one"

    anyio.run(run)


@settings(max_examples=3000)
@given(k1=keys, k2=keys)
def test_delete_does_not_affect_other_keys(k1, k2):
    if k1 == k2:
        return
    store = make_store()

    async def run():
        await store.set(k1, b"payload")
        await store.delete(k2)
        assert await store.exists(k1) is True

    anyio.run(run)

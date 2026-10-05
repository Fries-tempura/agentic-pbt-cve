"""get() must return None for a key that was never stored.

Keys are built the way litestar.config.response_cache.default_cache_key_builder
builds them: method + url.path + urlencode(sorted query params).
"""

import string
import tempfile
from pathlib import Path
from urllib.parse import urlencode

import anyio
from hypothesis import given, settings
from hypothesis import strategies as st

from litestar.stores.file import FileStore

word = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=6)


@st.composite
def cache_keys(draw):
    path = "/" + "/".join(draw(st.lists(word, min_size=1, max_size=4)))
    params = sorted(draw(st.lists(st.tuples(word, word), min_size=1, max_size=30)), key=lambda x: x[0])
    return "GET" + path + urlencode(params, doseq=True)


@settings(max_examples=200, deadline=None)
@given(key=cache_keys())
def test_get_returns_none_for_unset_key(key):
    store = FileStore(Path(tempfile.mkdtemp()))

    async def run():
        assert await store.get(key) is None

    anyio.run(run)


@settings(max_examples=200, deadline=None)
@given(key=cache_keys())
def test_set_get_round_trip(key):
    store = FileStore(Path(tempfile.mkdtemp()))

    async def run():
        await store.set(key, b"cached-body")
        assert await store.get(key) == b"cached-body"

    anyio.run(run)

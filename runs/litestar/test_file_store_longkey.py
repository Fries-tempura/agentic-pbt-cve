"""set()/get() must agree for the keys litestar itself generates.

Keys are built exactly the way ``litestar.config.response_cache.default_cache_key_builder``
builds them: ``request.method + request.url.path + urlencode(sorted_query_params)``.
"""

import string
import tempfile
from pathlib import Path
from urllib.parse import urlencode

import anyio
from hypothesis import given, settings
from hypothesis import strategies as st

from litestar.stores.file import FileStore

word = st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=8)
segments = st.lists(word, min_size=1, max_size=6)
params = st.lists(st.tuples(word, word), max_size=20)


@st.composite
def cache_keys(draw):
    """Mirror of default_cache_key_builder."""
    path = "/" + "/".join(draw(segments))
    query = sorted(draw(params), key=lambda x: x[0])
    return "GET" + path + urlencode(query, doseq=True)


def make_store():
    return FileStore(Path(tempfile.mkdtemp()))


@settings(max_examples=500)
@given(key=cache_keys(), value=st.binary(min_size=1, max_size=16))
def test_set_get_round_trip(key, value):
    store = make_store()

    async def run():
        await store.set(key, value)
        assert await store.get(key) == value, f"lost value for {len(key)}-char key"

    anyio.run(run)


@settings(max_examples=500)
@given(key=cache_keys())
def test_get_returns_none_for_unset_key(key):
    """get() is documented to return None when the key does not exist."""
    store = make_store()

    async def run():
        assert await store.get(key) is None

    anyio.run(run)

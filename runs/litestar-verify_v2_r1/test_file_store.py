import asyncio
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from litestar.stores.file import FileStore

# Alphabet chosen from the mechanism: alnum kept, others replaced by ord() digits,
# NFKD normalization applied first.
ALPHA = "a456-."  # "-"->45, "."->46: digits present so ord() expansions can be forged
keys = st.text(alphabet=ALPHA, min_size=1, max_size=4)


def run(coro):
    return asyncio.run(coro)


@settings(max_examples=300, deadline=None)
@given(ks=st.lists(keys, unique=True, min_size=2, max_size=12))
def test_distinct_keys_independent(ks):
    """CLAIM-1: each distinct key retrieves exactly its own value."""
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d) / "s")

        async def go():
            for i, k in enumerate(ks):
                await store.set(k, str(i).encode())
            return [await store.get(k) for k in ks]

        got = run(go())
        assert got == [str(i).encode() for i in range(len(ks))], list(zip(ks, got))


class StoreMachine(RuleBasedStateMachine):
    """CLAIM-2: set/delete/exists/get agree with a dict model."""

    def __init__(self):
        super().__init__()
        self.tmp = tempfile.TemporaryDirectory()
        self.store = FileStore(Path(self.tmp.name) / "s")
        self.model = {}

    def teardown(self):
        self.tmp.cleanup()

    @rule(k=keys, v=st.binary(max_size=8))
    def put(self, k, v):
        run(self.store.set(k, v))
        self.model[k] = v

    @rule(k=keys)
    def drop(self, k):
        run(self.store.delete(k))
        self.model.pop(k, None)

    @invariant()
    def matches(self):
        for k, v in self.model.items():
            assert run(self.store.get(k)) == v
            assert run(self.store.exists(k))


TestStoreMachine = StoreMachine.TestCase
TestStoreMachine.settings = settings(max_examples=100, deadline=None)


@settings(max_examples=100, deadline=None)
@given(ns=st.text(alphabet="ab0", min_size=1, max_size=3), k=st.text(alphabet="ab0", min_size=1, max_size=3))
def test_namespace_isolation(ns, k):
    """CLAIM-3: parent and child namespaces are isolated; parent bulk ops work with children."""
    with tempfile.TemporaryDirectory() as d:
        parent = FileStore(Path(d) / "s")
        child = parent.with_namespace(ns)

        async def go():
            await parent.set(k, b"parent")
            await child.set(k, b"child")
            p, c = await parent.get(k), await child.get(k)
            await parent.delete_expired()
            return p, c

        assert run(go()) == (b"parent", b"child")


@settings(max_examples=200, deadline=None)
@given(k=st.text(min_size=1, max_size=300), v=st.binary(max_size=8))
def test_set_then_get(k, v):
    """CLAIM-4: set followed by get returns the value for any str key."""
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d) / "s")

        async def go():
            await store.set(k, v)
            return await store.get(k)

        assert run(go()) == v

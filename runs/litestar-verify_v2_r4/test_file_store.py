import asyncio
import tempfile
from pathlib import Path

from hypothesis import given, settings, HealthCheck, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant

from litestar.stores.file import FileStore

# Alphabet chosen from the mechanism: _safe_file_name keeps alnum and replaces others by ord() digits;
# NFKD normalisation maps compatibility chars ("ﬁ", "①") onto ASCII.
KEY_ALPHA = "ab0145-_/.: ﬁ①"
keys = st.text(alphabet=KEY_ALPHA, min_size=1, max_size=6)
SETTINGS = settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck))


def run(coro):
    return asyncio.run(coro)


@SETTINGS
@given(ks=st.lists(keys, unique=True, min_size=2, max_size=8))
def test_distinct_keys_do_not_clobber(ks):
    """CLAIM-1: distinct keys keep their own values."""
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            for i, k in enumerate(ks):
                await s.set(k, str(i).encode())
            return [await s.get(k) for k in ks]
    got = run(go())
    assert got == [str(i).encode() for i in range(len(ks))], (ks, got)


@SETTINGS
@given(k=keys, v=st.binary())
def test_expires_in_none_without_expiry(k, v):
    """CLAIM-2: expires_in is None when no expiry was set."""
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(k, v)
            return await s.expires_in(k)
    assert run(go()) is None


@SETTINGS
@given(k=st.text(min_size=1, max_size=300), v=st.binary(max_size=20))
def test_set_get_roundtrip(k, v):
    """CLAIM-3: a set that returns normally makes the value retrievable."""
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            await s.set(k, v)
            return await s.get(k)
    assert run(go()) == v


def test_delete_expired_with_namespace():
    """CLAIM-4: delete_expired on the parent works with child namespaces and removes their expired items."""
    async def go():
        with tempfile.TemporaryDirectory() as d:
            s = FileStore(Path(d))
            child = s.with_namespace("child")
            await child.set("k", b"v", expires_in=1)
            await asyncio.sleep(1.1)
            await s.delete_expired()
            return (Path(d) / "child" / "k").exists()
    assert run(go()) is False


class StoreMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.tmp = tempfile.TemporaryDirectory()
        self.store = FileStore(Path(self.tmp.name))
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
        """CLAIM-5: exists/get agree with model."""
        for k, v in self.model.items():
            assert run(self.store.get(k)) == v, (k, self.model)


StoreMachine.TestCase.settings = settings(max_examples=100, deadline=None, stateful_step_count=10)
TestStore = StoreMachine.TestCase

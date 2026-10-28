import re
import time

from hypothesis import given, settings, strategies as st, assume
from twisted.mail import imap4

name_chars = st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters="*%/")
names = st.text(name_chars, min_size=1, max_size=20)


@given(names, names)
def test_wildcard_literal(wild, other):
    """CLAIM-1: non-wildcard characters are literal; never raises."""
    pat = imap4.wildcardToRegexp(wild, "/")
    assert pat.match(wild)
    if pat.match(other):
        assert other.upper().startswith(wild.upper())


class _Account(imap4.MemoryAccount):
    def _emptyMailbox(self, name, id):
        return object()


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=1, max_value=12))
def test_list_does_not_hang(n):
    """CLAIM-2: LIST pattern matching completes in bounded time."""
    acct = _Account("u")
    acct.addMailbox("a" * 30)
    t = time.perf_counter()
    acct.listMailboxes("", "%" * n + "b")
    assert time.perf_counter() - t < 1.0


@given(st.text())
def test_utf7_roundtrip(s):
    """CLAIM-3: imap4-utf-7 round trip, printable ASCII output."""
    assume(not any(0xD800 <= ord(c) <= 0xDFFF for c in s))
    e = s.encode("imap4-utf-7")
    assert all(0x20 <= b <= 0x7E for b in e)
    assert e.decode("imap4-utf-7") == s


ranges = st.lists(st.tuples(st.integers(1, 200), st.integers(1, 200)), min_size=1, max_size=8)


def build(rs):
    m = imap4.MessageSet()
    for a, b in rs:
        m.add(a, b)
    return m


@given(ranges)
def test_messageset_str_roundtrip(rs):
    """CLAIM-4: parseIdList(str(m)) == m."""
    m = build(rs)
    assert imap4.parseIdList(str(m).encode()) == m


@given(ranges, st.integers(1, 210))
def test_messageset_model(rs, x):
    """CLAIM-5: MessageSet agrees with a python set model."""
    m = build(rs)
    model = set()
    for a, b in rs:
        model |= set(range(min(a, b), max(a, b) + 1))
    assert set(m) == model
    assert len(m) == len(model)
    assert (x in m) == (x in model)


printable = st.binary().map(lambda b: bytes(c for c in b if 0x20 <= c < 0x7F))
nested = st.recursive(st.lists(printable, max_size=4), lambda ch: st.lists(st.one_of(printable, ch), max_size=4), max_leaves=12)


@given(nested)
def test_nested_roundtrip(x):
    """CLAIM-6: parseNestedParens(collapseNestedLists(x)) == x."""
    assert imap4.parseNestedParens(imap4.collapseNestedLists(x)) == x


@given(printable)
def test_splitquoted_quote(b):
    """CLAIM-7: splitQuoted(_quote(b)) == [b]."""
    assert imap4.splitQuoted(imap4._quote(b)) == [b]

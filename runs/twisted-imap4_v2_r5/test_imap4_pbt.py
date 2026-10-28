import time

from hypothesis import assume, given, settings, strategies as st

from twisted.mail import imap4
from twisted.mail.imap4 import (
    MemoryAccount,
    MessageSet,
    collapseNestedLists,
    parseIdList,
    parseNestedParens,
    splitQuoted,
    _quote,
)


@given(st.text())
@settings(max_examples=1000)
def test_utf7_roundtrip(s):
    """CLAIM-1: decode(encode(s)) == s."""
    assert s.encode("imap4-utf-7").decode("imap4-utf-7") == s


@given(st.text())
@settings(max_examples=1000)
def test_utf7_printable(s):
    """CLAIM-2: encoded bytes are printable ASCII."""
    assert all(0x20 <= b <= 0x7E for b in s.encode("imap4-utf-7"))


ranges = st.lists(
    st.tuples(st.integers(1, 60), st.integers(1, 60)), min_size=1, max_size=6
)


def build(rs):
    ms = MessageSet(*rs[0])
    for r in rs[1:]:
        ms = ms + MessageSet(*r)
    return ms


@given(ranges, st.integers(0, 70))
def test_messageset_semantics(rs, probe):
    """CLAIM-3: iteration, len and membership match the union of ranges."""
    ms = build(rs)
    expected = set()
    for a, b in rs:
        expected |= set(range(min(a, b), max(a, b) + 1))
    assert set(ms) == expected
    assert len(ms) == len(expected)
    assert (probe in ms) == (probe in expected)


@given(ranges)
def test_parseidlist_roundtrip(rs):
    """CLAIM-4: parseIdList(str(ms)) == ms."""
    ms = build(rs)
    assert parseIdList(str(ms).encode()) == ms


atom_bytes = st.binary(min_size=1).filter(lambda b: b"\r" not in b and b"\n" not in b)
nested = st.recursive(
    st.lists(atom_bytes, min_size=1, max_size=4),
    lambda inner: st.lists(st.one_of(atom_bytes, inner), min_size=1, max_size=4),
    max_leaves=10,
)


@given(nested)
@settings(max_examples=500)
def test_collapse_parse_roundtrip(x):
    """CLAIM-5: parseNestedParens(collapseNestedLists(x)) == x."""
    assert parseNestedParens(collapseNestedLists(x)) == x


@given(st.text(st.characters(codec="ascii", exclude_characters="\r\n"), max_size=30))
@settings(max_examples=500)
def test_list_wildcard_literal(w):
    """CLAIM-6: listMailboxes never raises; a wildcard without * or % matches only itself."""
    assume("*" not in w and "%" not in w and w.strip())
    acct = MemoryAccount("u")
    acct.addMailbox(w, object())
    acct.addMailbox("other", object())
    names = [n for n, _ in acct.listMailboxes("", w)]
    assert w.upper() in names
    assert all(n.upper() == w.upper() for n in names)


@given(st.integers(10, 30))
@settings(max_examples=5, deadline=None)
def test_list_wildcard_cost(n):
    """CLAIM-7: listMailboxes with short inputs completes quickly."""
    acct = MemoryAccount("u")
    acct.addMailbox("a" * n + "!", object())
    t = time.perf_counter()
    acct.listMailboxes("", "(a+)+$")
    assert time.perf_counter() - t < 1.0


@given(
    st.lists(
        st.binary(min_size=0).filter(lambda b: b'"' not in b and b"\\" not in b),
        min_size=1,
        max_size=6,
    )
)
def test_splitquoted(toks):
    """CLAIM-8: quoted tokens come back as single tokens."""
    assert splitQuoted(b" ".join(_quote(t) for t in toks)) == toks

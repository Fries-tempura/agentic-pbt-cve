import re
from hypothesis import given, settings, assume, strategies as st
from twisted.mail import imap4

text = st.text(st.characters(blacksurrogates=True) if False else st.characters(exclude_categories=("Cs",)))


@settings(max_examples=1000)
@given(text)
def test_utf7_roundtrip(s):
    assert s.encode("imap4-utf-7").decode("imap4-utf-7") == s


@settings(max_examples=500)
@given(st.text(st.characters(min_codepoint=0x20, max_codepoint=0x7E), min_size=1))
def test_utf7_printable_ascii_only(s):
    enc = s.encode("imap4-utf-7")
    assert all(0x20 <= b <= 0x7E for b in enc)


ranges = st.lists(
    st.tuples(st.integers(1, 200), st.one_of(st.none(), st.integers(1, 200))), min_size=1, max_size=6
)


def build(rs):
    m = imap4.MessageSet()
    for a, b in rs:
        m.add(a, b)
    return m


@settings(max_examples=1000)
@given(ranges, st.integers(1, 300))
def test_messageset_str_parse_roundtrip(rs, last):
    m = build(rs)
    parsed = imap4.parseIdList(str(m).encode("ascii"), last)
    m.last = last
    assert parsed == m


@settings(max_examples=1000)
@given(st.lists(st.tuples(st.integers(1, 200), st.integers(1, 200)), min_size=1, max_size=6))
def test_messageset_len_iter_contains(rs):
    m = build(rs)
    expected = set()
    for a, b in rs:
        expected |= set(range(min(a, b), max(a, b) + 1))
    assert list(m) == sorted(expected)
    assert len(m) == len(expected)
    for v in range(0, 205):
        assert (v in m) == (v in expected)


@settings(max_examples=1000)
@given(st.lists(st.tuples(st.integers(1, 200), st.integers(1, 200)), min_size=1, max_size=6),
       st.lists(st.tuples(st.integers(1, 200), st.integers(1, 200)), min_size=1, max_size=6))
def test_messageset_add_union(r1, r2):
    a, b = build(r1), build(r2)
    assert set(a + b) == set(a) | set(b)


atom_bytes = st.binary(min_size=1).filter(lambda b: b"\r" not in b and b"\n" not in b and len(b) <= 1000)
nested = st.recursive(
    st.one_of(st.binary(max_size=30)),
    lambda ch: st.lists(ch, max_size=4),
    max_leaves=12,
)


@settings(max_examples=1000)
@given(st.lists(nested, max_size=5))
def test_collapse_parse_roundtrip(items):
    s = imap4.collapseNestedLists(items)
    assert imap4.parseNestedParens(s) == items


@settings(max_examples=1000)
@given(st.lists(st.binary(max_size=20).filter(lambda b: b"\r" not in b and b"\n" not in b), max_size=5))
def test_quote_splitquoted_roundtrip(words):
    s = b" ".join(imap4._quote(w) for w in words)
    assert imap4.splitQuoted(s) == words


name_chars = st.characters(min_codepoint=0x21, max_codepoint=0x7E).filter(lambda c: c not in "*%/")


@settings(max_examples=1000)
@given(st.text(name_chars, min_size=1), st.text(name_chars, min_size=1))
def test_wildcard_literal_name_matches_only_itself(a, b):
    assume(a.upper() != b.upper())
    r = imap4.wildcardToRegexp(a, "/")
    assert r.match(a)
    assert not r.match(b)

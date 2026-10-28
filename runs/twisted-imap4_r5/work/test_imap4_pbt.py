import re
from hypothesis import given, settings, assume, strategies as st
from twisted.mail import imap4

literal_chars = st.characters(min_codepoint=0x20, max_codepoint=0x7e, blacklist_characters="*%")
names = st.text(literal_chars, min_size=1)


@settings(max_examples=500)
@given(names)
def test_wildcard_literal_name_matches_itself(name):
    # A pattern with no wildcard chars must match the identical mailbox name
    assert imap4.wildcardToRegexp(name, "/").match(name)


@settings(max_examples=500)
@given(names, names)
def test_wildcard_literal_name_no_false_match(name, other):
    assume(name.lower() != other.lower())
    m = imap4.wildcardToRegexp(name, "/").fullmatch(other)
    assert not m


@settings(max_examples=1000)
@given(st.text())
def test_utf7_roundtrip(s):
    enc = s.encode("imap4-utf-7")
    assert enc.decode("imap4-utf-7") == s


@settings(max_examples=500)
@given(st.lists(st.tuples(st.integers(1, 10**6), st.integers(1, 10**6) | st.none()), min_size=1))
def test_messageset_str_parseidlist_roundtrip(pairs):
    ms = imap4.MessageSet()
    for a, b in pairs:
        ms.add(a, b)
    parsed = imap4.parseIdList(str(ms).encode())
    assert parsed == ms


@settings(max_examples=500)
@given(st.lists(st.tuples(st.integers(1, 200), st.integers(1, 200)), min_size=1))
def test_messageset_len_iter_contains(pairs):
    ms = imap4.MessageSet()
    expected = set()
    for a, b in pairs:
        ms.add(a, b)
        expected |= set(range(min(a, b), max(a, b) + 1))
    assert set(ms) == expected
    assert len(ms) == len(expected)
    for x in range(0, 202):
        assert (x in ms) == (x in expected)


atom_bytes = st.binary(min_size=1).filter(lambda b: b"\r" not in b and b"\n" not in b)
nested = st.recursive(
    st.binary().filter(lambda b: b"\r" not in b and b"\n" not in b and len(b) <= 1000),
    lambda ch: st.lists(ch),
    max_leaves=20,
)


@settings(max_examples=1000)
@given(st.lists(nested))
def test_collapse_parse_roundtrip(items):
    assume(not any(isinstance(x, bytes) and x == b"NIL" for x in items))
    out = imap4.collapseNestedLists(items)
    assert imap4.parseNestedParens(out) == items


@settings(max_examples=1000)
@given(st.binary().filter(lambda b: b"\r" not in b and b"\n" not in b))
def test_quote_splitquoted_roundtrip(b):
    assert imap4.splitQuoted(imap4._quote(b)) == [b]


@settings(max_examples=1000)
@given(st.binary().filter(lambda b: b"\r" not in b and b"\n" not in b))
def test_quoted_string_parses_as_one_token(b):
    # The module's own tests keep backslashes raw, so only check that a quoted
    # string produced by _quote parses back as exactly one token.
    assert len(imap4.splitQuoted(imap4._quote(b))) == 1

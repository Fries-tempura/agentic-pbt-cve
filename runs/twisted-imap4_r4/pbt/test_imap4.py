from hypothesis import given, settings, strategies as st, assume
from twisted.mail import imap4
from twisted.mail.imap4 import MessageSet, parseIdList, parseNestedParens, collapseNestedLists, splitQuoted, _quote

@settings(max_examples=2000)
@given(st.text())
def test_utf7_roundtrip(s):
    enc = s.encode("imap4-utf-7")
    assert all(0x20 <= b < 0x7f for b in enc)
    assert enc.decode("imap4-utf-7") == s

bstr = st.binary(max_size=30)
nested = st.recursive(st.lists(bstr), lambda c: st.lists(st.one_of(bstr, c)), max_leaves=20)

@settings(max_examples=2000)
@given(st.lists(st.one_of(bstr, nested)))
def test_parens_roundtrip(items):
    s = collapseNestedLists(items)
    assert parseNestedParens(s) == items

@settings(max_examples=2000)
@given(st.lists(st.binary().filter(lambda b: b != b"NIL")))
def test_splitquoted_roundtrip(words):
    s = b" ".join(_quote(w) for w in words)
    assert splitQuoted(s) == words

rng = st.tuples(st.integers(1, 200), st.integers(1, 200))
@settings(max_examples=2000)
@given(st.lists(rng, min_size=1), st.integers(1, 300))
def test_messageset(ranges, probe):
    ms = MessageSet()
    expected = set()
    for a, b in ranges:
        ms.add(a, b)
        expected |= set(range(min(a, b), max(a, b) + 1))
    assert set(ms) == expected
    assert len(ms) == len(expected)
    assert (probe in ms) == (probe in expected)
    assert parseIdList(str(ms).encode()) == ms

@settings(max_examples=2000)
@given(st.lists(st.tuples(st.one_of(st.none(), st.integers(1, 200)), st.one_of(st.none(), st.integers(1, 200))), min_size=1), st.integers(1, 300))
def test_messageset_star(ranges, last):
    assume(not any(a is None and b is None for a, b in ranges))
    ms = MessageSet()
    for a, b in ranges:
        ms.add(a, b)
    s = str(ms).encode()
    ms2 = parseIdList(s)
    assert ms2 == ms
    ms.last = last
    expected = set()
    for a, b in ranges:
        a = last if a is None else a
        b = last if b is None else b
        expected |= set(range(min(a, b), max(a, b) + 1))
    assert set(ms) == expected
    assert parseIdList(s, last) == ms

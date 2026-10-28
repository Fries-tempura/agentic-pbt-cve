import time
from hypothesis import given, settings, strategies as st, assume
from twisted.mail import imap4

@settings(max_examples=1000)
@given(st.text())
def test_utf7_roundtrip(s):
    enc = s.encode("imap4-utf-7")
    assert enc.decode("imap4-utf-7") == s

@settings(max_examples=500)
@given(st.text())
def test_utf7_ascii_output(s):
    enc = s.encode("imap4-utf-7")
    assert all(0x20 <= b < 0x7f for b in enc)

pos = st.integers(1, 200)
rng = st.tuples(pos, st.one_of(st.none(), pos))

@settings(max_examples=1000)
@given(st.lists(rng, min_size=1))
def test_messageset_str_roundtrip(ranges):
    ms = imap4.MessageSet()
    for a, b in ranges:
        ms.add(a, b)
    parsed = imap4.parseIdList(str(ms).encode())
    assert parsed == ms, (str(ms), str(parsed))

@settings(max_examples=1000)
@given(st.lists(rng, min_size=1), st.integers(200, 300))
def test_messageset_len_iter_contains(ranges, last):
    ms = imap4.MessageSet()
    for a, b in ranges:
        ms.add(a, b)
    ms.last = last
    items = list(ms)
    assert len(items) == len(ms)
    assert len(set(items)) == len(items)
    expected = set()
    for a, b in ranges:
        b = last if b is None else b
        expected |= set(range(min(a, b), max(a, b) + 1))
    assert set(items) == expected
    for i in range(1, last + 2):
        assert (i in ms) == (i in expected)

@settings(max_examples=1000)
@given(st.lists(rng, min_size=1), st.lists(rng, min_size=1))
def test_messageset_add_union(r1, r2):
    a = imap4.MessageSet(); b = imap4.MessageSet()
    for x, y in r1: a.add(x, y)
    for x, y in r2: b.add(x, y)
    c = a + b
    d = imap4.MessageSet()
    for x, y in r1 + r2: d.add(x, y)
    assert c == d

atom_bytes = st.binary(min_size=1).filter(lambda b: b"\r" not in b and b"\n" not in b)
nested = st.recursive(
    st.binary(max_size=30),
    lambda ch: st.lists(ch, max_size=4),
    max_leaves=10,
)

def norm(x):
    return x

@settings(max_examples=1000)
@given(st.lists(nested, max_size=5))
def test_collapse_parse_roundtrip(items):
    s = imap4.collapseNestedLists(items)
    assert imap4.parseNestedParens(s) == items, s

@settings(max_examples=1000)
@given(st.lists(st.binary().filter(lambda b: b"\r" not in b and b"\n" not in b), max_size=5))
def test_splitquoted_quote_roundtrip(words):
    s = b" ".join(imap4._quote(w) for w in words)
    assert imap4.splitQuoted(s) == words, s

@settings(max_examples=500)
@given(st.dates(min_value=__import__("datetime").date(1000,1,1)))
def test_parsetime(d):
    s = "%02d-%s-%04d" % (d.day, imap4._MONTH_NAMES[d.month], d.year)
    t = imap4.parseTime(s)
    assert (t.tm_year, t.tm_mon, t.tm_mday) == (d.year, d.month, d.day)

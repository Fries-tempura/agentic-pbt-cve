import time

from hypothesis import given, settings, strategies as st

from twisted.mail import imap4

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


@settings(max_examples=1000)
@given(st.text())
def test_utf7_round_trip(s):
    """CLAIM-1: imap4-utf-7 decode(encode(s)) == s."""
    assert s.encode("imap4-utf-7").decode("imap4-utf-7") == s


leaf = st.binary(min_size=1).filter(lambda b: b != b"NIL" and b == b.rstrip())
nested = st.recursive(
    st.lists(leaf, min_size=1, max_size=4),
    lambda inner: st.lists(st.one_of(leaf, inner), min_size=1, max_size=4),
    max_leaves=10,
)


@settings(max_examples=1000)
@given(nested)
def test_collapse_parse_round_trip(items):
    """CLAIM-2: parseNestedParens(collapseNestedLists(x)) == x."""
    assert imap4.parseNestedParens(imap4.collapseNestedLists(items)) == items


ranges = st.lists(
    st.tuples(st.integers(1, 200), st.integers(1, 200)), min_size=1, max_size=8
)


def build(rs):
    ms = imap4.MessageSet()
    for a, b in rs:
        ms.add(a, b)
    return ms


@given(ranges)
def test_messageset_union(rs):
    """CLAIM-3: MessageSet contents equal the union of inclusive unordered ranges."""
    ms = build(rs)
    expected = set()
    for a, b in rs:
        expected |= set(range(min(a, b), max(a, b) + 1))
    assert set(ms) == expected
    assert len(ms) == len(expected)
    for v in range(0, 202):
        assert (v in ms) == (v in expected)


@given(ranges)
def test_parseidlist_str_round_trip(rs):
    """CLAIM-4: parseIdList(str(ms)) == ms."""
    ms = build(rs)
    assert imap4.parseIdList(str(ms).encode("ascii")) == ms


def _time_parse(n):
    s = b",".join(b"%d" % (2 * i + 1) for i in range(n))
    t = time.perf_counter()
    imap4.parseIdList(s)
    return time.perf_counter() - t


@settings(max_examples=5, deadline=None)
@given(st.integers(1500, 2500))
def test_parseidlist_linear(n):
    """CLAIM-5: parseIdList cost is linear in the number of parts."""
    small = min(_time_parse(n) for _ in range(2))
    big = min(_time_parse(2 * n) for _ in range(2))
    assert big / small < 3.0, (n, small, big)


@settings(max_examples=20, deadline=None, database=None)
@given(st.integers(1, 3000))
def test_parse_nested_parens_deep(depth):
    """CLAIM-6: balanced nesting of any depth parses without raising."""
    s = b"(" * depth + b"a" + b")" * depth
    result = imap4.parseNestedParens(s)
    assert isinstance(result, list)


@given(st.integers(1, 28), st.sampled_from(range(12)), st.integers(1000, 9999))
def test_parse_time(d, mi, y):
    """CLAIM-7: parseTime('DD-Mon-YYYY') recovers day, month and year."""
    t = imap4.parseTime("%02d-%s-%04d" % (d, MONTHS[mi], y))
    assert (t.tm_mday, t.tm_mon, t.tm_year) == (d, mi + 1, y)

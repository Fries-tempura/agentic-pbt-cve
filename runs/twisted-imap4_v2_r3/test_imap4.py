import re, time
from hypothesis import given, settings, strategies as st, assume
from twisted.mail import imap4
from twisted.mail.imap4 import MessageSet, parseIdList, parseNestedParens, collapseNestedLists


class _Box:
    pass


def _account(names):
    acct = imap4.MemoryAccount("u")
    acct._emptyMailbox = lambda name, id: _Box()
    for n in names:
        try:
            acct.addMailbox(n)
        except imap4.MailboxCollision:
            pass
    return acct


def ref_match(w, name):
    # slow obvious glob matcher
    w, name = w.upper(), name.upper()
    def m(i, j):
        if i == len(w):
            return j == len(name)
        c = w[i]
        if c == "*":
            return any(m(i + 1, k) for k in range(j, len(name) + 1))
        if c == "%":
            k = j
            while True:
                if m(i + 1, k):
                    return True
                if k == len(name) or name[k] == "/":
                    return False
                k += 1
        return j < len(name) and name[j] == c and m(i + 1, j + 1)
    return m(0, 0)


seg = st.text(alphabet="abcXY.", min_size=1, max_size=4)
names = st.lists(st.lists(seg, min_size=1, max_size=3).map("/".join), min_size=1, max_size=6)
wild = st.text(alphabet="abcXY./*%", max_size=8)


@settings(max_examples=500)
@given(names, wild)
def test_list_matches_reference(ns, w):
    """CLAIM-1: listMailboxes returns exactly the names matched by the glob."""
    acct = _account(ns)
    got = {n for n, _ in acct.listMailboxes("", w)}
    want = {n for n in acct.mailboxes if ref_match(w, n)}
    assert got == want


@given(names, st.text(max_size=10))
def test_list_no_crash(ns, w):
    """CLAIM-2: listMailboxes never raises for any wildcard text."""
    assert isinstance(_account(ns).listMailboxes("", w), list)


@settings(max_examples=30, deadline=None)
@given(st.integers(min_value=10, max_value=30))
def test_list_cost(n):
    """CLAIM-3: LIST cost does not blow up with the number of wildcards."""
    acct = _account(["a" * 30])
    t = time.perf_counter()
    acct.listMailboxes("", "%" * n + "b")
    assert time.perf_counter() - t < 1.0


@given(st.text())
def test_utf7_roundtrip(s):
    """CLAIM-4: imap4-utf-7 round trip, 7-bit printable output."""
    b = s.encode("imap4-utf-7")
    assert all(0x20 <= c < 0x7F for c in b)
    assert b.decode("imap4-utf-7") == s


@given(st.lists(st.tuples(st.integers(1, 1000), st.integers(1, 1000)), min_size=1))
def test_messageset_roundtrip(pairs):
    """CLAIM-5: parseIdList(str(ms)) == ms."""
    ms = MessageSet()
    for a, b in pairs:
        ms.add(a, b)
    assert parseIdList(str(ms).encode()) == ms


atom = st.binary(min_size=1, max_size=6).filter(lambda b: all(0x20 <= c < 0x7F for c in b))
nested = st.recursive(st.lists(atom, max_size=4), lambda c: st.lists(st.one_of(atom, c), max_size=4), max_leaves=10)


@given(nested)
def test_parens_roundtrip(x):
    """CLAIM-6: parseNestedParens(collapseNestedLists(x)) == x."""
    assert parseNestedParens(collapseNestedLists(x)) == x

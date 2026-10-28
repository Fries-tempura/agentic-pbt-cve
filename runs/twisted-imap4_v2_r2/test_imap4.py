import re
import time

from hypothesis import given, settings, strategies as st

from twisted.mail import imap4
from twisted.mail.imap4 import (
    MemoryAccount, MessageSet, parseIdList, splitQuoted, wildcardToRegexp, _quote,
)


class Box:
    def __init__(self, name):
        self.name = name


class Acct(MemoryAccount):
    def _emptyMailbox(self, name, id):
        return Box(name)


name_chars = st.sampled_from("ABCXYZ.+()[]?^$|\\{}0123")
segment = st.text(name_chars, min_size=1, max_size=5)
names = st.lists(segment, min_size=1, max_size=3).map("/".join)


def _make(ns):
    a = Acct("u")
    for n in ns:
        try:
            a.addMailbox(n)
        except imap4.MailboxCollision:
            pass
    return a


@settings(max_examples=500)
@given(st.lists(names, min_size=1, max_size=5), st.data())
def test_literal_wildcard_selects_exact_name(ns, data):
    """CLAIM-1: a wildcard without '*'/'%' lists exactly the mailbox of that name."""
    a = _make(ns)
    w = data.draw(st.one_of(st.sampled_from(ns), names))
    try:
        got = sorted(n for n, _ in a.listMailboxes("", w))
    except re.error as e:
        raise AssertionError(f"re.error for wildcard {w!r}: {e}")
    expected = sorted(n for n in a.mailboxes if n == w.upper())
    assert got == expected, (w, got, expected)


@settings(max_examples=300)
@given(st.lists(names, min_size=1, max_size=5), st.data())
def test_percent_does_not_cross_delimiter(ns, data):
    """CLAIM-1: 'P%' never returns a name with '/' after prefix P."""
    a = _make(ns)
    prefix = data.draw(st.text(st.sampled_from("ABCXYZ0123"), max_size=3))
    for n, _ in a.listMailboxes("", prefix + "%"):
        assert n.upper().startswith(prefix.upper())
        assert "/" not in n[len(prefix):], (prefix + "%", n)


@settings(max_examples=300, deadline=None)
@given(st.text(st.characters(min_codepoint=0x20, max_codepoint=0x7E), max_size=30))
def test_wildcard_never_raises(w):
    """CLAIM-2: any printable wildcard compiles."""
    wildcardToRegexp(w, "/")


def test_wildcard_cost_bounded():
    """CLAIM-2: matching cost does not explode with wildcard length (25-char wildcard, 24-char name)."""
    import subprocess, sys
    code = ("from twisted.mail.imap4 import wildcardToRegexp;"
            "wildcardToRegexp('%' * 24 + 'X', '/').match('A' * 24)")
    try:
        subprocess.run([sys.executable, "-c", code], timeout=5, check=True)
    except subprocess.TimeoutExpired:
        raise AssertionError("listMailboxes wildcard '%'*24+'X' did not finish in 5s")


@settings(max_examples=1000)
@given(st.text().filter(lambda s: not any(0xD800 <= ord(c) <= 0xDFFF for c in s)))
def test_utf7_round_trip(s):
    """CLAIM-3: imap4-utf-7 round trip."""
    assert s.encode("imap4-utf-7").decode("imap4-utf-7") == s


@given(st.binary().filter(lambda b: all(0x20 <= c < 0x7F and c != 0x5C for c in b)))
def test_split_quoted_round_trip(b):
    """CLAIM-4: splitQuoted(_quote(b)) == [b]."""
    assert splitQuoted(_quote(b)) == [b]


@given(st.lists(st.tuples(st.integers(1, 10**6), st.integers(1, 10**6)), min_size=1))
def test_parse_id_list_round_trip(rs):
    """CLAIM-5: parseIdList(str(ms)) == ms."""
    ms = MessageSet()
    for lo, hi in rs:
        ms.add(lo, hi)
    assert parseIdList(str(ms).encode()) == ms

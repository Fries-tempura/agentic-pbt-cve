from hypothesis import given, settings, strategies as st
from twisted.mail.imap4 import IMAP4Server, _quote, parseNestedParens
from twisted.internet.testing import StringTransport

printable = st.binary().map(lambda b: bytes(c for c in b if 0x20 <= c < 0x7f))

@settings(max_examples=1000)
@given(printable, printable)
def test_client_quote_server_astring_roundtrip(user, password):
    s = IMAP4Server(); s.makeConnection(StringTransport())
    line = _quote(user) + b" " + _quote(password)
    u, rest = s.arg_astring(line)
    p, rest2 = s.arg_astring(rest)
    assert (u, p) == (user, password)

@settings(max_examples=1000)
@given(st.lists(printable, min_size=1))
def test_quote_parse_roundtrip(words):
    assert parseNestedParens(b" ".join(_quote(w) for w in words)) == words

import base64, re, time
from hypothesis import given, settings, strategies as st
from twisted.mail import imap4

imap4.modified_base64 = lambda s: base64.b64encode(s.encode("utf-16-be")).rstrip(b"=").replace(b"/", b",")

@given(st.text())
@settings(max_examples=3000)
def t(s):
    e = s.encode("imap4-utf-7")
    assert e.decode("imap4-utf-7") == s and all(0x20 <= b <= 0x7e for b in e)
t()

def w(wildcard, delim=None):
    percent = "(?:.*?)" if delim is None else "(?:(?:[^%s])*?)" % re.escape(delim)
    return re.compile("".join("(?:.*?)" if c == "*" else percent if c == "%" else re.escape(c) for c in wildcard) + r"\Z", re.I)
imap4.wildcardToRegexp = w
a = imap4.MemoryAccount("u")
for n in ["INBOX", "INBOXES", "AXB", "a" * 27 + "!", "X/Y/Z", "X/Y"]:
    a.addMailbox(n, object())
L = lambda p: [n for n, _ in a.listMailboxes("", p)]
tt = time.perf_counter(); print(L("(a+)+$"), round(time.perf_counter() - tt, 3))
print(L("INBOX"), L("a.b"), L("["), L("INBOX*"), L("X/%"), L("X/*"))

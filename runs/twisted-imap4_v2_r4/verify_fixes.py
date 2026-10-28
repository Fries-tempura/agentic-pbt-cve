import base64, functools, string, time
from hypothesis import given, settings, strategies as st
from twisted.mail import imap4
from twisted.python.compat import iterbytes

def modified_base64(s):
    return base64.b64encode(s.encode("utf-16-be")).rstrip(b"=").replace(b"/", b",")
imap4.modified_base64 = modified_base64

def splitQuoted(s):
    s = s.strip()
    result = []
    word = []
    inQuote = inWord = escaped = False
    for c in iterbytes(s):
        if inQuote:
            if escaped:
                word.append(c)
                escaped = False
            elif c == b"\\":
                escaped = True
            elif c == b'"':
                inQuote = False
                result.append(b"".join(word))
                word = []
            else:
                word.append(c)
        elif c == b'"':
            inQuote = True
        elif c in string.whitespace.encode("ascii"):
            if inWord:
                w = b"".join(word)
                result.append(None if w == b"NIL" else w)
                word = []
                inWord = False
        else:
            inWord = True
            word.append(c)
    if inQuote:
        raise imap4.MismatchedQuoting(s)
    if inWord:
        w = b"".join(word)
        result.append(None if w == b"NIL" else w)
    return result
imap4.splitQuoted = splitQuoted

_orig = imap4.parseIdList
def parseIdList(s, lastMessageId=None):
    ranges = []
    class Collect(imap4.MessageSet):
        def clean(self): pass
    res = Collect()
    res2 = _orig.__wrapped__ if hasattr(_orig, "__wrapped__") else None
    return None

@settings(max_examples=2000)
@given(st.text())
def test_utf7(s):
    assert s.encode("imap4-utf-7").decode("imap4-utf-7") == s

leaf = st.binary(min_size=1).filter(lambda b: b != b"NIL")
nested = st.recursive(st.lists(leaf, min_size=1, max_size=4),
    lambda i: st.lists(st.one_of(leaf, i), min_size=1, max_size=4), max_leaves=10)

@settings(max_examples=2000)
@given(nested)
def test_rt(items):
    assert imap4.parseNestedParens(imap4.collapseNestedLists(items)) == items

def test_list_delim():
    assert imap4.parseNestedParens(rb'(\HasNoChildren) "\\" INBOX') == [[b"\\HasNoChildren"], b"\\", b"INBOX"]

import base64, string
from hypothesis import given, settings, strategies as st
from twisted.mail import imap4
from twisted.python.compat import iterbytes

def modified_base64(s):
    return base64.b64encode(s.encode("utf-16-be")).rstrip(b"=").replace(b"/", b",")
imap4.modified_base64 = modified_base64

def splitQuoted(s):
    s = s.strip()
    result, word = [], []
    inQuote = inWord = escaped = False
    ws = string.whitespace.encode("ascii")
    for c in iterbytes(s):
        if inQuote:
            if escaped:
                word.append(c); escaped = False
            elif c == b"\\":
                escaped = True
            elif c == b'"':
                inQuote = False
                result.append(b"".join(word)); word = []
            else:
                word.append(c)
        elif c == b'"':
            inQuote = True
        elif c in ws:
            if inWord:
                w = b"".join(word)
                result.append(None if w == b"NIL" else w)
                word = []; inWord = False
        else:
            inWord = True; word.append(c)
    if inQuote:
        raise imap4.MismatchedQuoting(s)
    if inWord:
        w = b"".join(word)
        result.append(None if w == b"NIL" else w)
    return result
imap4.splitQuoted = splitQuoted

@settings(max_examples=2000)
@given(st.text())
def test_utf7(s):
    assert s.encode("imap4-utf-7").decode("imap4-utf-7") == s

@settings(max_examples=2000)
@given(st.lists(st.binary().filter(lambda b: b"\r" not in b and b"\n" not in b), max_size=5))
def test_split(words):
    assert imap4.splitQuoted(b" ".join(imap4._quote(w) for w in words)) == words

nested = st.recursive(st.binary(max_size=30), lambda ch: st.lists(ch, max_size=4), max_leaves=10)
@settings(max_examples=2000)
@given(st.lists(nested, max_size=5))
def test_nested(items):
    assert imap4.parseNestedParens(imap4.collapseNestedLists(items)) == items

import inspect
from hypothesis import given, settings, strategies as st
from twisted.mail import imap4

src = inspect.getsource(imap4.splitQuoted)
old = """    for i, c in enumerate(iterbytes(s)):
        if c == qu:
            if i and s[i - 1 : i] == esc:
                word.pop()
                word.append(qu)
            elif not inQuote:"""
new = """    escaped = False
    for i, c in enumerate(iterbytes(s)):
        if inQuote and escaped:
            word.append(c)
            escaped = False
        elif inQuote and c == esc:
            escaped = True
        elif c == qu:
            if not inQuote:"""
assert old in src
exec(src.replace(old, new), imap4.__dict__)

leaf = st.binary(min_size=1).filter(lambda b: b != b"NIL" and b == b.rstrip())
nested = st.recursive(st.lists(leaf, min_size=1, max_size=4),
    lambda i: st.lists(st.one_of(leaf, i), min_size=1, max_size=4), max_leaves=10)

@settings(max_examples=3000)
@given(nested)
def test_rt(items):
    assert imap4.parseNestedParens(imap4.collapseNestedLists(items)) == items

def test_list_delim():
    assert imap4.parseNestedParens(rb'(\HasNoChildren) "\\" INBOX') == [[b"\\HasNoChildren"], b"\\", b"INBOX"]

def test_flags_unchanged():
    assert imap4.parseNestedParens(rb'FLAGS (\Seen \Answered) "a\"b" NIL') == [b"FLAGS", [b"\\Seen", b"\\Answered"], b'a"b', None]

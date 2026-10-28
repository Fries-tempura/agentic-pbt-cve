# Bug Report: twisted.mail.imap4 parseNestedParens/splitQuoted mishandle escaped backslashes in quoted strings

**Target**: `twisted.mail.imap4.parseNestedParens`, `twisted.mail.imap4.splitQuoted`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`collapseNestedLists` (via `_quote`) escapes `\` as `\\`, and RFC 3501 requires that escape. The client-side parser, however, never unescapes `\\`:
- A quoted string that contains a backslash comes back with the backslash doubled.
- A quoted string that ends in a backslash raises `MismatchedQuoting`, because `splitQuoted` reads the closing `"` as an escaped quote.

## Property-Based Test

```python
@settings(max_examples=1000)
@given(st.lists(st.binary(max_size=20).filter(lambda b: b"\r" not in b and b"\n" not in b), max_size=5))
def test_quote_splitquoted_roundtrip(words):
    s = b" ".join(imap4._quote(w) for w in words)
    assert imap4.splitQuoted(s) == words
```

**Failing input**: `words=[b'\\']`. A related test, `parseNestedParens(collapseNestedLists(items)) == items`, fails with `items=[b'\\\x00']`.

## Reproducing the Bug

```python
from twisted.mail import imap4
from twisted.internet.testing import StringTransport

def list_response(line):
    c = imap4.IMAP4Client()
    c.makeConnection(StringTransport())
    c.state = "AUTH"
    c.lineReceived(b"* OK ready")
    res = []
    c.list("", "*").addBoth(res.append)
    c.dataReceived(line + b"\r\n0001 OK done\r\n")
    return res

print(list_response(b'* LIST () "/" "a\\\\b"'))  # [[((), '/', 'a\\\\b')]]  expected 'a\\b'
list_response(b'* LIST () "/" "C:\\\\"')         # MismatchedQuoting raised
print(imap4.parseNestedParens(imap4.collapseNestedLists([b"a\\b"])))  # [b'a\\\\b']
```

## Why This Is A Bug

In RFC 3501's formal syntax, `quoted-specials` (`"` and `\`) appear escaped inside quoted strings. Twisted's own server escapes them through `_quote`, but `IMAP4Client` doesn't decode them. Mailbox names, ENVELOPE subjects and addresses that contain backslashes come back corrupted, and a value that ends in a backslash makes the whole response fail to parse.

## Fix

Make `splitQuoted` track escape state while it is inside a quoted string, instead of looking at the previous byte:

```diff
-    for i, c in enumerate(iterbytes(s)):
-        if c == qu:
-            if i and s[i - 1 : i] == esc:
-                word.pop()
-                word.append(qu)
-            elif not inQuote:
+    escaped = False
+    for i, c in enumerate(iterbytes(s)):
+        if inQuote and escaped:
+            word.append(c)
+            escaped = False
+        elif inQuote and c == esc:
+            escaped = True
+        elif c == qu:
+            if not inQuote:
                 inQuote = True
```

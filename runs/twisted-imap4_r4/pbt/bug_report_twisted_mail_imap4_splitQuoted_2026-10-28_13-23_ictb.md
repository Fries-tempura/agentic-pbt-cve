# Bug Report: twisted.mail.imap4 splitQuoted/parseNestedParens fail on `\\` and keep escapes in quoted strings

**Target**: `twisted.mail.imap4.splitQuoted`, `twisted.mail.imap4.parseNestedParens`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

`splitQuoted` decides whether a `"` is escaped by checking only whether the previous byte is a backslash. In a quoted string that ends in an escaped backslash (`"\\"`), the closing quote is therefore read as escaped, and the parse fails with `MismatchedQuoting`. Escapes are also never decoded: `"a\\b"` comes back as `a\\b`. `IMAP4Client` parses every server response with these functions, so a normal response like `* LIST (\HasNoChildren) "\\" INBOX` (a mailbox whose hierarchy delimiter is backslash) crashes the client. The pending `list()` Deferred never fires.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from twisted.mail.imap4 import splitQuoted, parseNestedParens, collapseNestedLists, _quote

@settings(max_examples=2000)
@given(st.lists(st.binary().filter(lambda b: b != b"NIL")))
def test_splitquoted_roundtrip(words):
    s = b" ".join(_quote(w) for w in words)
    assert splitQuoted(s) == words
```

**Failing input**: `words=[b'\\']`

## Reproducing the Bug

```python
from twisted.mail.imap4 import splitQuoted, IMAP4Client
from twisted.internet.testing import StringTransport

print(splitQuoted(rb'"a\\b"'))          # [b'a\\\\b'], expected [b'a\\b']
try:
    splitQuoted(rb'"foo\\"')
except Exception as e:
    print(repr(e))                      # MismatchedQuoting

c = IMAP4Client()
c.makeConnection(StringTransport())
c.lineReceived(b'* OK [IMAP4rev1] ready')
res = []
c.list(b"", b"*").addBoth(res.append)
c.lineReceived(rb'* LIST (\HasNoChildren) "\\" INBOX')   # logs MismatchedQuoting
c.lineReceived(b'0001 OK LIST done')
print(res)                              # [] - Deferred never fires
```

## Why This Is A Bug

RFC 3501 quoted strings escape `"` and `\` with a backslash. The module's own `_quote` produces this encoding, but `splitQuoted` / `parseNestedParens` can't parse it back. A quoted value ending in a backslash, such as the common `"\\"` hierarchy delimiter in LIST/LSUB responses, raises `MismatchedQuoting` inside the client's response handling. Other values come back still escaped.

## Fix

Track escape state while scanning instead of checking only the previous byte, and drop the escaping backslash:

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
```

(`parseNestedParens` already keeps `\x` pairs together inside quotes, so the fix in `splitQuoted` covers both.)

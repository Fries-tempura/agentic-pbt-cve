# Bug Report: twisted.mail.imap4 parseNestedParens/splitQuoted don't unescape backslashes

**Target**: `twisted.mail.imap4.parseNestedParens`, `twisted.mail.imap4.splitQuoted`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`_quote` and `collapseNestedLists` escape `\` as `\\` inside quoted strings, as RFC 3501 requires. But `parseNestedParens` and `splitQuoted`, the parsers the client uses on server responses, never turn `\\` back into `\`. Quoted strings that contain a backslash therefore come back doubled. If the backslash is the last character, parsing fails with `MismatchedQuoting`.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from twisted.mail import imap4

tree = st.recursive(st.binary(), lambda c: st.lists(c), max_leaves=20)

@settings(max_examples=1000)
@given(st.lists(tree))
def test_collapse_parse_roundtrip(items):
    s = imap4.collapseNestedLists(items)
    assert imap4.parseNestedParens(s) == items

@settings(max_examples=1000)
@given(st.lists(st.binary().filter(lambda b: b"\r" not in b and b"\n" not in b), min_size=1))
def test_quote_splitQuoted(words):
    s = b" ".join(imap4._quote(w) for w in words)
    assert imap4.splitQuoted(s) == words
```

**Failing input**: `items=[b'\\']` (raises `MismatchedQuoting`), `items=[b'\\\x00']` (returns `[b'\\\\\x00']`)

## Reproducing the Bug

```python
from twisted.mail import imap4

wire = imap4.collapseNestedLists([b"C:\\dir", b"x"])
assert wire == b'"C:\\\\dir" "x"'
assert imap4.parseNestedParens(wire) == [b"C:\\\\dir", b"x"]

imap4.parseNestedParens(imap4.collapseNestedLists([[b"C:\\", b"x"]]))
```

The last line raises `MismatchedQuoting`.

## Why This Is A Bug

In RFC 3501's grammar, `quoted-specials` (`"` and `\`) are escaped with a backslash inside a quoted string. Twisted's encoder (`_quote`, used by `collapseNestedLists` and so by the server's FETCH/ENVELOPE/BODYSTRUCTURE responses) follows this. Its decoder doesn't:

- `parseNestedParens` copies the two-byte `\\` sequence into the token unchanged.
- `splitQuoted` only handles `\"`. It decides whether a quote is escaped by looking at the single previous byte. So in `"...\\"` the closing quote is taken as escaped, and the call raises `MismatchedQuoting`.

Any FETCH response field with a backslash (a subject or address like `C:\temp`, a filename in BODYSTRUCTURE) is corrupted or makes the `IMAP4Client` parse fail. That includes Twisted's own server talking to Twisted's own client.

## Fix

Unescape quoted-specials while tokenizing in `splitQuoted`, and track escapes as parser state instead of looking back one byte:

```diff
--- a/src/twisted/mail/imap4.py
+++ b/src/twisted/mail/imap4.py
@@ def splitQuoted(s):
-    inQuote = inWord = False
+    inQuote = inWord = escaped = False
@@
     for i, c in enumerate(iterbytes(s)):
-        if c == qu:
-            if i and s[i - 1 : i] == esc:
-                word.pop()
-                word.append(qu)
-            elif not inQuote:
+        if inQuote and escaped:
+            word.append(c)
+            escaped = False
+        elif inQuote and c == esc:
+            escaped = True
+        elif c == qu:
+            if not inQuote:
                 inQuote = True
```

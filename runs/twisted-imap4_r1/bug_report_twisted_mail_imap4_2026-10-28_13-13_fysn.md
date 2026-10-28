# Bug Report: twisted.mail.imap4 parseNestedParens/splitQuoted reject quoted strings ending in an escaped backslash

**Target**: `twisted.mail.imap4.splitQuoted` (and `parseNestedParens`, which uses it)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

`splitQuoted` treats any `"` that comes right after a backslash as an escaped quote, even when that backslash is itself escaped. Valid quoted strings such as `"\\"` or `"C:\\"` therefore raise `MismatchedQuoting`.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from twisted.mail import imap4

@settings(max_examples=1000)
@given(st.lists(st.binary().filter(lambda b: b"\r" not in b and b"\n" not in b), max_size=5))
def test_splitquoted_quote_roundtrip(words):
    s = b" ".join(imap4._quote(w) for w in words)
    assert imap4.splitQuoted(s) == words, s
```

**Failing input**: `words=[b'\\']`, where `_quote` produces `b'"\\\\"'`

## Reproducing the Bug

```python
from twisted.mail import imap4

imap4.parseNestedParens(rb'() "\\" INBOX')
```

```
twisted.mail.imap4.MismatchedQuoting: b'"\\\\" INBOX'
```

## Why This Is A Bug

In RFC 3501 §9, `quoted = DQUOTE *QUOTED-CHAR DQUOTE` with `QUOTED-CHAR =/ "\" quoted-specials`, so `"\\"` is a valid quoted string holding a single backslash. The module's own `_quote` produces exactly this form for any value ending in a backslash. The check `s[i - 1 : i] == esc` only looks at the previous byte, so it treats the closing quote as escaped and the parser runs off the end of the string.

This is reachable in real use:
- **Client:** `Command.finish` calls `parseNestedParens` on every untagged response. A server that uses `\` as its hierarchy delimiter (`* LIST () "\\" INBOX`), or that returns a mailbox name or envelope field ending in `\`, makes the response handler raise.
- **Server:** `arg_searchkeys` calls `parseNestedParens`, so `SEARCH SUBJECT "C:\\"` is rejected.

## Fix

Track escape state instead of looking only at the previous byte. The patch below keeps the existing behaviour that the test suite pins down (`\"` becomes `"`, and other backslash sequences are kept as-is). With it, `src/twisted/mail/test/test_imap.py` has no new failures.

```diff
--- a/src/twisted/mail/imap4.py
+++ b/src/twisted/mail/imap4.py
@@ -4626,9 +4626,10 @@
     esc = _matchingString("\x5c", s)
     empty = _matchingString("", s)
     nil = _matchingString("NIL", s)
-    for i, c in enumerate(iterbytes(s)):
+    escaped = False
+    for c in iterbytes(s):
         if c == qu:
-            if i and s[i - 1 : i] == esc:
+            if escaped:
                 word.pop()
                 word.append(qu)
             elif not inQuote:
@@ -4654,6 +4655,7 @@
             inWord = False
         elif inWord or inQuote:
             word.append(c)
+        escaped = c == esc and not escaped
 
     if inQuote:
         raise MismatchedQuoting(s)
```

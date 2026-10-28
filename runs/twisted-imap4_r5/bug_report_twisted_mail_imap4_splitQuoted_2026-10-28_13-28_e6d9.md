# Bug Report: twisted.mail.imap4.splitQuoted / parseNestedParens Reject a Quoted String Ending in an Escaped Backslash

**Target**: `twisted.mail.imap4.splitQuoted` (also reached through `parseNestedParens`, which the client uses to parse server responses)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

`splitQuoted` decides whether a `"` is escaped by looking only at the previous byte (`s[i-1] == b"\\"`). It doesn't notice when that backslash is itself escaped. A valid quoted string ending in `\\`, such as `"C:\\"`, therefore has its closing quote treated as an escaped quote, and parsing fails with `MismatchedQuoting`. That includes strings produced by the module's own `_quote` and `collapseNestedLists`.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from twisted.mail import imap4

@settings(max_examples=1000)
@given(st.binary().filter(lambda b: b"\r" not in b and b"\n" not in b))
def test_quoted_string_parses_as_one_token(b):
    assert len(imap4.splitQuoted(imap4._quote(b))) == 1
```

**Failing input**: `b=b'\\'`

## Reproducing the Bug

```python
from twisted.mail import imap4

wire = imap4.collapseNestedLists([b"C:\\"])
assert wire == b'"C:\\\\"'
imap4.parseNestedParens(wire)
# twisted.mail._except.MismatchedQuoting

imap4.parseNestedParens(b'(\\HasNoChildren) "/" "C:\\\\"')
# MismatchedQuoting -- a valid LIST response line
```

## Why This Is A Bug

In RFC 3501, `"C:\\"` is a well-formed quoted string: `\\` is an escaped backslash, and the final `"` closes the string. `IMAP4Client` uses `parseNestedParens` to parse LIST/LSUB, FETCH ENVELOPE and BODYSTRUCTURE responses. Any server value whose quoted form ends in a backslash therefore makes the client fail, for example a mailbox name or a Subject like `C:\`. Twisted's own server encoding (`collapseNestedLists` → `_quote`) produces exactly this form, so Twisted can't parse its own output.

(Not reported here: `splitQuoted` also leaves `\\` and `\x` as-is instead of unescaping them. The existing tests in `test_quotedSplitter` and `test_parenParser` assert that behaviour, so it is intended.)

## Fix

Track whether the previous byte was an *unescaped* backslash instead of looking at `s[i-1]`:

```diff
--- a/src/twisted/mail/imap4.py
+++ b/src/twisted/mail/imap4.py
@@ def splitQuoted(s):
     s = s.strip()
     result = []
     word = []
-    inQuote = inWord = False
+    inQuote = inWord = escaped = False
@@
     for i, c in enumerate(iterbytes(s)):
         if c == qu:
-            if i and s[i - 1 : i] == esc:
+            if escaped:
                 word.pop()
                 word.append(qu)
@@
         elif inWord or inQuote:
             word.append(c)
+        escaped = c == esc and not escaped
 
     if inQuote:
         raise MismatchedQuoting(s)
```

With this patch, the property passes and so does the existing `twisted.mail.test.test_imap` suite (342 successes).

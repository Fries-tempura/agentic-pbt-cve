# Bug Report: twisted.mail.imap4 parseNestedParens mishandles escaped backslashes in quoted strings

**Target**: `twisted.mail.imap4.parseNestedParens` / `splitQuoted`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

Inside a quoted string, `\\` is the RFC 3501 escape for one backslash, but the parser never turns it back into one. Values containing a backslash come back with it doubled. A value that ends in a backslash raises `MismatchedQuoting`. One example is the very common LIST hierarchy delimiter `"\\"`.

## Property-Based Test

```python
leaf = st.binary(min_size=1).filter(lambda b: b != b"NIL" and b == b.rstrip())
nested = st.recursive(
    st.lists(leaf, min_size=1, max_size=4),
    lambda inner: st.lists(st.one_of(leaf, inner), min_size=1, max_size=4),
    max_leaves=10,
)

@settings(max_examples=1000)
@given(nested)
def test_collapse_parse_round_trip(items):
    """CLAIM-2: parseNestedParens(collapseNestedLists(x)) == x."""
    assert imap4.parseNestedParens(imap4.collapseNestedLists(items)) == items
```

**Failing input**: `items=[b'\\']` (raises `MismatchedQuoting`) and `items=[b'\\\x00']` (returns `[b'\\\\\x00']`)

## Reproducing the Bug

```python
from twisted.mail.imap4 import collapseNestedLists, parseNestedParens

print(parseNestedParens(collapseNestedLists([b"a\\b"])))
print(parseNestedParens(rb'"Re: C:\\temp"'))
parseNestedParens(rb'(\HasNoChildren) "\\" INBOX')
```

Output:

```
[b'a\\\\b']
[b'Re: C:\\\\temp']
twisted.mail._except.MismatchedQuoting: b'"\\\\" INBOX'
```

## Why This Is A Bug

In RFC 3501 §9, `quoted = DQUOTE *QUOTED-CHAR DQUOTE` and `QUOTED-CHAR = ... / "\" quoted-specials`. That makes `"\\"` the one-character string `\`. Twisted's own encoder, `_quote` (used by `collapseNestedLists`), escapes this way. The parser does not reverse it:

1. `parseNestedParens` keeps escape pairs verbatim.
2. `splitQuoted` only checks whether the byte before a `"` is `\`. It never removes the escaping `\` from `\\`.
3. In `"\\"`, the closing quote follows a backslash, so `splitQuoted` treats it as escaped. The string never closes and `MismatchedQuoting` is raised.

`IMAP4Client` sends every untagged response through `parseNestedParens`. Effects:

- A server LIST response with a backslash delimiter (`* LIST (...) "\\" INBOX`) makes `client.list()` fail.
- ENVELOPE subjects or addresses containing a backslash come back corrupted.

## Fix

```diff
--- a/src/twisted/mail/imap4.py
+++ b/src/twisted/mail/imap4.py
@@ def splitQuoted(s):
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
             else:
```

With this patch, the round-trip test passes on 3,000 examples. The LIST delimiter case parses to `[[b'\\HasNoChildren'], b'\\', b'INBOX']`. Flags such as `\Seen` outside quotes are unchanged.

# Bug Report: twisted.mail.imap4.parseNestedParens mishandles the escaped backslash `\\` in quoted strings

**Target**: `twisted.mail.imap4.parseNestedParens` (via `splitQuoted`)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

The client-side response parser does not unescape `\\` inside a quoted string. `"a\\b"` is returned with two backslashes instead of one. `"\\"`, which encodes a single backslash, raises `MismatchedQuoting`. As a result, it cannot parse what Twisted's own `collapseNestedLists` produces, or valid RFC 3501 responses such as `* LIST () "\\" INBOX`.

## Property-Based Test

```python
atom_bytes = st.binary(min_size=1).filter(lambda b: b"\r" not in b and b"\n" not in b)
nested = st.recursive(
    st.lists(atom_bytes, min_size=1, max_size=4),
    lambda inner: st.lists(st.one_of(atom_bytes, inner), min_size=1, max_size=4),
    max_leaves=10,
)


@given(nested)
@settings(max_examples=500)
def test_collapse_parse_roundtrip(x):
    """CLAIM-5: parseNestedParens(collapseNestedLists(x)) == x."""
    assert parseNestedParens(collapseNestedLists(x)) == x
```

**Failing input**: `x=[b'\\']`

## Reproducing the Bug

```python
from twisted.mail.imap4 import collapseNestedLists, parseNestedParens

print(parseNestedParens(collapseNestedLists([b"a\\b"])))  # [b'a\\\\b'], expected [b'a\\b']
parseNestedParens(b'LIST () "\\\\" INBOX')                # MismatchedQuoting
```

## Why This Is A Bug

RFC 3501 §4.3 / §9 (`quoted-specials`) define `\\` as the escape for one backslash, and `_quote` escapes that way. `parseNestedParens` copies the two bytes `\\` unchanged. `splitQuoted` then sees a `"` preceded by `\`, treats it as an escaped quote, and either keeps reading past the end of the string or leaves both backslashes in the result. `IMAP4Client` parses every untagged response with this function (`Command.finish`). If a server uses `\` as its hierarchy delimiter, or a response contains a quoted string ending in a backslash, `dispatchCommand` gets an exception and drops the connection. Other backslashes are returned doubled, which corrupts the data.

## Fix

Unescape while scanning quoted strings in `splitQuoted`, rather than looking back one byte:

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

# Bug Report: twisted.mail.imap4 quoted-string parsing mishandles escaped backslashes

**Target**: `twisted.mail.imap4.splitQuoted` (and `parseNestedParens`, which uses it via `collapseStrings`)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`splitQuoted` decides that a `"` is escaped by looking only at the single preceding byte. A quoted string that ends in an escaped backslash therefore fails:

- `"\\"` is the correct quoting of a single `\`, as `_quote(b"\\")` produces.
- `splitQuoted` sees the final `"` as escaped and raises `MismatchedQuoting`.

`\\` is also never unescaped, so `"\\ "` comes back as `b'\\\\ '` instead of `b'\\ '`. Twisted's own serializer (`collapseNestedLists`) and its client-side parser (`parseNestedParens`) therefore do not round-trip any byte string that contains a backslash.

## Property-Based Test

```python
@given(printable)
def test_splitquoted_quote(b):
    """CLAIM-7: splitQuoted(_quote(b)) == [b]."""
    assert imap4.splitQuoted(imap4._quote(b)) == [b]


@given(nested)
def test_nested_roundtrip(x):
    """CLAIM-6: parseNestedParens(collapseNestedLists(x)) == x."""
    assert imap4.parseNestedParens(imap4.collapseNestedLists(x)) == x
```

**Failing input**: `b=b'\\'` (raises `MismatchedQuoting`); `b=b'\\ '` (returns `[b'\\\\ ']`); `x=[b'\\']`

## Reproducing the Bug

```python
from twisted.mail import imap4

print(imap4.splitQuoted(b'"a\\\\b"'))
imap4.parseNestedParens(imap4.collapseNestedLists([b"\\"]))
```

## Why This Is A Bug

`splitQuoted` documents that quoted tokens "remain as a single token". In RFC 3501 quoted strings, `\\` is the escape for a backslash, and `_quote` follows that rule. The client parses server responses (for example LIST, ENVELOPE and BODYSTRUCTURE) with `parseNestedParens`, which uses `splitQuoted`. As a result, a mailbox name, address or subject containing a backslash either:

- aborts parsing with `MismatchedQuoting`, when the backslash comes right before the closing quote; or
- is returned with the escape still doubled.

## Fix

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

(The rest of the loop is unchanged. Inside a quoted string, a backslash consumes the next byte literally, so `\\` decodes to `\` and `\"` decodes to `"`.)

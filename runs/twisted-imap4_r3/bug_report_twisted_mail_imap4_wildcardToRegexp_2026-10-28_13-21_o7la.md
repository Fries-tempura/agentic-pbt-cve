# Bug Report: twisted.mail.imap4 wildcardToRegexp treats mailbox names as regexes and matches prefixes

**Target**: `twisted.mail.imap4.wildcardToRegexp` (used by `MemoryAccountWithoutNamespaces.listMailboxes`)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`wildcardToRegexp` only rewrites `*` and `%`. Every other character in the client-supplied LIST pattern goes to `re.compile` without escaping, and the caller uses `.match` with no end anchor. As a result:
- `.` matches any character.
- Characters like `(`, `[`, `\`, `+` and `?` raise `re.error`, or change the meaning of the pattern.
- A literal name also matches every mailbox that starts with it.

## Property-Based Test

```python
name_chars = st.characters(min_codepoint=0x21, max_codepoint=0x7E).filter(lambda c: c not in "*%/")

@settings(max_examples=1000)
@given(st.text(name_chars, min_size=1), st.text(name_chars, min_size=1))
def test_wildcard_literal_name_matches_only_itself(a, b):
    assume(a.upper() != b.upper())
    r = imap4.wildcardToRegexp(a, "/")
    assert r.match(a)
    assert not r.match(b)
```

**Failing inputs**: `a="0", b="00"` (prefix match), `a="("` (re.error), `a="\\C"` (bad escape), etc.

## Reproducing the Bug

```python
from twisted.mail import imap4

acct = imap4.MemoryAccount("u")
for n in ["INBOX2", "foo", "foobar", "aXb", "Work (old)"]:
    acct.addMailbox(n, object())

print([n for n, _ in acct.listMailboxes("", "INBOX")])       # ['INBOX2']
print([n for n, _ in acct.listMailboxes("", "FOO")])         # ['FOO', 'FOOBAR']
print([n for n, _ in acct.listMailboxes("", "A.B")])         # ['AXB']
print([n for n, _ in acct.listMailboxes("", "WORK (OLD)")])  # []
imap4.wildcardToRegexp("Foo(", "/")                          # re.error
```

## Why This Is A Bug

RFC 3501 §6.3.8 defines `*` and `%` as the only wildcards. Every other character must match itself, and the whole name has to match. Right now `LIST "" "INBOX"` returns `INBOX2` and misses real names that contain parentheses. Because the pattern comes from the client, a remote user can also send any regex they like to the server, including patterns with catastrophic backtracking.

## Fix

```diff
 def wildcardToRegexp(wildcard: str, delim: str | None = None) -> re.Pattern[str]:
-    wildcard = wildcard.replace("*", "(?:.*?)")
+    wildcard = re.escape(wildcard)
+    wildcard = wildcard.replace(re.escape("*"), "(?:.*?)")
+    pct = re.escape("%")
     if delim is None:
-        wildcard = wildcard.replace("%", "(?:.*?)")
+        wildcard = wildcard.replace(pct, "(?:.*?)")
     else:
-        wildcard = wildcard.replace("%", "(?:(?:[^%s])*?)" % re.escape(delim))
-    return re.compile(wildcard, re.I)
+        wildcard = wildcard.replace(pct, "(?:(?:[^%s])*?)" % re.escape(delim))
+    return re.compile(wildcard + r"\Z", re.I)
```

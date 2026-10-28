# Bug Report: twisted.mail.imap4.wildcardToRegexp Does Not Escape Regex Metacharacters in LIST Patterns

**Target**: `twisted.mail.imap4.wildcardToRegexp` (used by `MemoryAccount.listMailboxes`, i.e. the LIST/LSUB commands)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`wildcardToRegexp` turns the IMAP `*` and `%` wildcards into regex fragments, but it passes every other character of the client-supplied pattern straight into `re.compile`. Characters that are legal in mailbox names but special in regex (`.`, `(`, `?`, `+`, `[`, `$`, `\`, ...) therefore behave as regex syntax. As a result:

- a LIST pattern matches the wrong mailboxes;
- some patterns make the server raise `re.error`;
- an authenticated client can submit a catastrophic-backtracking regex (ReDoS).

## Property-Based Test

```python
from hypothesis import given, settings, assume, strategies as st
from twisted.mail import imap4

literal_chars = st.characters(min_codepoint=0x20, max_codepoint=0x7e, blacklist_characters="*%")
names = st.text(literal_chars, min_size=1)

@settings(max_examples=500)
@given(names)
def test_wildcard_literal_name_matches_itself(name):
    assert imap4.wildcardToRegexp(name, "/").match(name)

@settings(max_examples=500)
@given(names, names)
def test_wildcard_literal_name_no_false_match(name, other):
    assume(name.lower() != other.lower())
    assert not imap4.wildcardToRegexp(name, "/").fullmatch(other)
```

**Failing input**: `name='('` (raises `re.error: missing ), unterminated subpattern`); `name='?', other='0'`; also `'\\'`, `'['`, `'$'`, `')'`

## Reproducing the Bug

```python
import time
from twisted.mail import imap4

class Account(imap4.MemoryAccount):
    def _emptyMailbox(self, name, id):
        return object()

acc = Account("u")
for n in ["Lists.2024", "ListsX2024", "A" * 26 + "!"]:
    acc.addMailbox(n)

print(sorted(n for n, _ in acc.listMailboxes("", "Lists.2024")))
# ['LISTS.2024', 'LISTSX2024']  -- 'ListsX2024' should not match

acc.listMailboxes("", "Work(")
# re.PatternError: missing ), unterminated subpattern at position 4

t = time.time(); acc.listMailboxes("", "(A+)+$"); print(time.time() - t)
# ~2 s measured for a 27-char name (nested quantifier, exponential backtracking)
```

## Why This Is A Bug

In RFC 3501 §6.3.8 only `*` and `%` are wildcards in a LIST pattern. Every other character must match itself, and `.` and `(` are common in mailbox names (e.g. `Lists.2024`). The pattern comes from the network (`IMAP4Server._listWork` → `account.listMailboxes`), so:

- listings are wrong;
- clients can trigger unhandled exceptions;
- an authenticated user can tie up the reactor thread for arbitrary time with a nested-quantifier pattern.

## Fix

```diff
--- a/src/twisted/mail/imap4.py
+++ b/src/twisted/mail/imap4.py
@@ def wildcardToRegexp(wildcard: str, delim: str | None = None) -> re.Pattern[str]:
-    wildcard = wildcard.replace("*", "(?:.*?)")
-    if delim is None:
-        wildcard = wildcard.replace("%", "(?:.*?)")
-    else:
-        wildcard = wildcard.replace("%", "(?:(?:[^%s])*?)" % re.escape(delim))
-    return re.compile(wildcard, re.I)
+    parts = []
+    for c in wildcard:
+        if c == "*" or (c == "%" and delim is None):
+            parts.append("(?:.*?)")
+        elif c == "%":
+            parts.append("(?:(?:[^%s])*?)" % re.escape(delim))
+        else:
+            parts.append(re.escape(c))
+    return re.compile("".join(parts), re.I)
```

With this patch, the existing `twisted.mail.test.test_imap` suite passes (including `test_wildcard` and `test_wildcardNoDelim`).

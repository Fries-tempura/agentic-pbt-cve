# Bug Report: twisted.mail.imap4.wildcardToRegexp does not escape the client's LIST pattern (ReDoS, crash, wrong matches)

**Target**: `twisted.mail.imap4.wildcardToRegexp` / `MemoryAccount.listMailboxes` / `IMAP4Server` LIST and LSUB
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`wildcardToRegexp` only rewrites `*` and `%` and passes every other character of the client's LIST/LSUB pattern to `re.compile` unchanged. Any authenticated client can therefore inject a regular expression. A pattern like `(a+)+$` blocks the server's reactor for exponential time (5.3 s against a 27-character mailbox name, doubling with each extra character). Patterns such as `[` make the command fail, and `.` or `?` match the wrong mailboxes.

## Property-Based Test

```python
@given(st.text(st.characters(codec="ascii", exclude_characters="\r\n"), max_size=30))
@settings(max_examples=500)
def test_list_wildcard_literal(w):
    """CLAIM-6: listMailboxes never raises; a wildcard without * or % matches only itself."""
    assume("*" not in w and "%" not in w and w.strip())
    acct = MemoryAccount("u")
    acct.addMailbox(w, object())
    acct.addMailbox("other", object())
    names = [n for n, _ in acct.listMailboxes("", w)]
    assert w.upper() in names
    assert all(n.upper() == w.upper() for n in names)


@given(st.integers(10, 30))
@settings(max_examples=5, deadline=None)
def test_list_wildcard_cost(n):
    """CLAIM-7: listMailboxes with short inputs completes quickly."""
    acct = MemoryAccount("u")
    acct.addMailbox("a" * n + "!", object())
    t = time.perf_counter()
    acct.listMailboxes("", "(a+)+$")
    assert time.perf_counter() - t < 1.0
```

**Failing input**: `w='['` (re.PatternError), `w=')'`, `w='?'`, `w='.'` (matches `OTHER`); `n=25` (> 1 s)

## Reproducing the Bug

```python
import time
from twisted.internet.testing import StringTransport
from twisted.mail import imap4

class Box:
    def getFlags(self): return []
    def getHierarchicalDelimiter(self): return "/"

acct = imap4.MemoryAccount("u")
acct.addMailbox("a" * 27 + "!", Box())
server = imap4.IMAP4Server()
server.makeConnection(StringTransport())
server.account, server.state = acct, "auth"
t = time.perf_counter()
server.dataReceived(b'A1 LIST "" "(a+)+$"\r\n')
print(time.perf_counter() - t)   # ~5.3 s, doubles per extra 'a'

acct.addMailbox("AXB", Box())
print([n for n, _ in acct.listMailboxes("", "a.b")])   # ['AXB'], expected []
acct.listMailboxes("", "[")                            # re.PatternError
```

## Why This Is A Bug

`IMAP4Client.list` and `IAccount.listMailboxes` say that only `*` and `%` are wildcards, and RFC 3501 §6.3.8 agrees: every other character is a literal part of the mailbox name. Because the code compiles client-controlled text as a regular expression, any logged-in user can stall the single-threaded reactor, and with it every connection the process serves, using a single short command. Mailbox names containing ordinary characters like `.`, `?`, `+`, `(` or `[` also get listed incorrectly or cause errors.

A related problem is that `listMailboxes` uses `re.match`, which anchors only at the start of the name. A plain pattern `INBOX` therefore also returns `INBOXES`, while RFC 3501 requires the pattern to match the whole name.

## Fix

```diff
 def wildcardToRegexp(wildcard: str, delim: str | None = None) -> re.Pattern[str]:
-    wildcard = wildcard.replace("*", "(?:.*?)")
-    if delim is None:
-        wildcard = wildcard.replace("%", "(?:.*?)")
-    else:
-        wildcard = wildcard.replace("%", "(?:(?:[^%s])*?)" % re.escape(delim))
-    return re.compile(wildcard, re.I)
+    if delim is None:
+        percent = "(?:.*?)"
+    else:
+        percent = "(?:(?:[^%s])*?)" % re.escape(delim)
+    pattern = "".join(
+        "(?:.*?)" if c == "*" else percent if c == "%" else re.escape(c)
+        for c in wildcard
+    )
+    return re.compile(pattern + r"\Z", re.I)
```

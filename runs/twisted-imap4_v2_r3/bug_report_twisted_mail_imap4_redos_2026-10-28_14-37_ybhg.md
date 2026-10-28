# Bug Report: twisted.mail.imap4 LIST wildcard causes catastrophic regex backtracking (ReDoS)

**Target**: `twisted.mail.imap4.wildcardToRegexp` / `MemoryAccount.listMailboxes` / `IMAP4Server` LIST, LSUB
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`wildcardToRegexp` turns every `%` (and `*`) of a client-supplied LIST/LSUB wildcard into a lazy `(?:[^/]*?)` / `(?:.*?)` group and runs the result with Python's backtracking `re` engine. A wildcard of N `%` followed by a non-matching character takes time that grows roughly like len(name)^N. An authenticated client can send one short `LIST` command and block the single-threaded reactor for minutes, which stops the server for every connection.

## Property-Based Test

```python
@settings(max_examples=30, deadline=None)
@given(st.integers(min_value=10, max_value=30))
def test_list_cost(n):
    """CLAIM-3: LIST cost does not blow up with the number of wildcards."""
    acct = _account(["a" * 30])
    t = time.perf_counter()
    acct.listMailboxes("", "%" * n + "b")
    assert time.perf_counter() - t < 1.0
```

**Failing input**: `n=10` (and any larger value)

## Reproducing the Bug

```python
import time
from twisted.mail import imap4

acct = imap4.MemoryAccount("u")
acct._emptyMailbox = lambda name, id: object()
acct.addMailbox("a" * 30)

for n in (4, 6, 8, 10):
    t = time.perf_counter()
    acct.listMailboxes("", "%" * n + "b")
    print(n, round(time.perf_counter() - t, 3))
```

Measured: 4 → 0.000 s, 6 → 0.015 s, 8 → 0.41 s, 10 → 7.6 s. Each further `%` multiplies the time again; 12 `%` already takes minutes.

Through the protocol (`IMAP4Server._listWork` calls `listMailboxes` synchronously):

```python
import time
from twisted.mail import imap4
from twisted.internet.testing import StringTransport

acct = imap4.MemoryAccount("u")
acct.mailboxes["A" * 30] = object()
s = imap4.IMAP4Server()
s.makeConnection(StringTransport())
s.account, s.state = acct, "auth"
t = time.perf_counter()
s.dataReceived(b'a1 LIST "" "%%%%%%%%%b"\r\n')
print(time.perf_counter() - t)   # ~1.8 s for a 12-byte wildcard
```

## Why This Is A Bug

A LIST wildcard is untrusted client input. Matching a glob against a mailbox name can be done in time linear in the input sizes. Here a few bytes from the client can block the event loop for an unbounded time, so any account holder can deny service to everyone on the server.

## Fix

Do not compile client input into a backtracking regex. Match the glob directly with a linear-time NFA simulation:

```diff
--- a/src/twisted/mail/imap4.py
+++ b/src/twisted/mail/imap4.py
@@ def wildcardToRegexp(wildcard: str, delim: str | None = None) -> re.Pattern[str]:
-def wildcardToRegexp(wildcard: str, delim: str | None = None) -> re.Pattern[str]:
-    wildcard = wildcard.replace("*", "(?:.*?)")
-    if delim is None:
-        wildcard = wildcard.replace("%", "(?:.*?)")
-    else:
-        wildcard = wildcard.replace("%", "(?:(?:[^%s])*?)" % re.escape(delim))
-    return re.compile(wildcard, re.I)
+def _wildcardMatch(wildcard: str, name: str, delim: str | None = None) -> bool:
+    """
+    Match C{name} against an IMAP LIST wildcard in O(len(wildcard) * len(name))
+    time: '*' matches anything, '%' anything but C{delim}, every other
+    character matches itself (case-insensitively).
+    """
+    wildcard, name = wildcard.casefold(), name.casefold()
+
+    def close(states):
+        out, todo = set(states), list(states)
+        while todo:
+            i = todo.pop()
+            if i < len(wildcard) and wildcard[i] in "*%" and i + 1 not in out:
+                out.add(i + 1)
+                todo.append(i + 1)
+        return out
+
+    states = close({0})
+    for ch in name:
+        nxt = set()
+        for i in states:
+            if i == len(wildcard):
+                continue
+            w = wildcard[i]
+            if w == "*" or (w == "%" and ch != delim):
+                nxt.add(i)
+            elif w == ch:
+                nxt.add(i + 1)
+        states = close(nxt)
+        if not states:
+            return False
+    return len(wildcard) in states
@@ class MemoryAccountWithoutNamespaces:
     def listMailboxes(self, ref, wildcard):
         ref = self._inferiorNames(_parseMbox(ref.upper()))
-        wildcard = wildcardToRegexp(wildcard, "/")
-        return [(i, self.mailboxes[i]) for i in ref if wildcard.match(i)]
+        return [(i, self.mailboxes[i]) for i in ref if _wildcardMatch(wildcard, i, "/")]
```
(If `wildcardToRegexp` must be kept for third-party `IAccount` implementations, it should at least `re.escape` every non-wildcard segment and be documented as requiring `fullmatch`; that fixes the injection and anchoring but not the super-linear backtracking, so the non-regex matcher above is the real fix.)

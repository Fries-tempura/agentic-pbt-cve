# Bug Report: twisted.mail.imap4 LIST wildcard is treated as a raw, unanchored regex

**Target**: `twisted.mail.imap4.wildcardToRegexp` / `MemoryAccount.listMailboxes`
**Severity**: Medium
**Bug Type**: Contract
**Date**: 2026-10-28

## Summary

`IAccount.listMailboxes` documents the wildcard as a glob in which only `*` and `%` are special, and `%` "will not match across hierarchical boundaries". `wildcardToRegexp` does not escape the other characters, and `listMailboxes` uses `re.match` (prefix match) rather than a full match. As a result:
- `.` matches any character, so `A.B` lists `AXB`
- `(`, `[`, `+` and similar characters raise `re.error`, and the server answers `BAD Server error`
- any prefix matches, so `LIST "" "IN"` returns `INBOX`, and `LIST "" ""` or `LIST "" "%"` return every mailbox, including `INBOX/SUB`

## Property-Based Test

```python
seg = st.text(alphabet="abcXY.", min_size=1, max_size=4)
names = st.lists(st.lists(seg, min_size=1, max_size=3).map("/".join), min_size=1, max_size=6)
wild = st.text(alphabet="abcXY./*%", max_size=8)

@settings(max_examples=500)
@given(names, wild)
def test_list_matches_reference(ns, w):
    """CLAIM-1: listMailboxes returns exactly the names matched by the glob."""
    acct = _account(ns)
    got = {n for n, _ in acct.listMailboxes("", w)}
    want = {n for n in acct.mailboxes if ref_match(w, n)}
    assert got == want

@given(names, st.text(max_size=10))
def test_list_no_crash(ns, w):
    """CLAIM-2: listMailboxes never raises for any wildcard text."""
    assert isinstance(_account(ns).listMailboxes("", w), list)
```
(`ref_match` is a straightforward recursive glob matcher; see `test_imap4.py`.)

**Failing input**: `ns=['X'], w=''` (returns `['X']`, expected `[]`); `test_list_no_crash` fails on a wildcard containing a regex metacharacter such as `(`.

## Reproducing the Bug

```python
from twisted.mail import imap4

acct = imap4.MemoryAccount("u")
acct._emptyMailbox = lambda name, id: object()
for n in ["INBOX", "INBOX/SUB", "AXB", "FOO"]:
    acct.addMailbox(n)

print([n for n, _ in acct.listMailboxes("", "")])     # ['INBOX', 'INBOX/SUB', 'AXB', 'FOO']
print([n for n, _ in acct.listMailboxes("", "IN")])   # ['INBOX', 'INBOX/SUB']
print([n for n, _ in acct.listMailboxes("", "%")])    # includes 'INBOX/SUB'
print([n for n, _ in acct.listMailboxes("", "A.B")])  # ['AXB']
acct.listMailboxes("", "(")                           # re.PatternError
```

## Why This Is A Bug

It breaks the documented contract of `IAccount.listMailboxes` (interfaces.py:983-986) and RFC 3501 §6.3.8. Clients get mailboxes they did not ask for. `%` does not respect the hierarchy delimiter. Legitimate mailbox names that contain characters such as `(`, `+` or `[` cannot be listed.

## Fix

This is the same fix as the ReDoS report: replace the regex with a literal glob matcher that matches the whole name.

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

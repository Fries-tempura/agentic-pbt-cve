# Bug Report: twisted.mail.imap4.wildcardToRegexp treats LIST patterns as raw regular expressions (injection and ReDoS)

**Target**: `twisted.mail.imap4.wildcardToRegexp` (used by `MemoryAccountWithoutNamespaces.listMailboxes`, which is reached from the server's `LIST`/`LSUB`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`wildcardToRegexp` turns `*` and `%` into regex fragments but passes every other character of the client's pattern to `re.compile` without escaping it. An authenticated client sending `LIST`/`LSUB` can:

- crash the command with a malformed pattern such as `[`;
- get wrong matches, because `.` matches any character;
- inject an arbitrary regex such as `(a+)+b` and stall the single-threaded reactor with catastrophic backtracking.

Legitimate wildcards cause the same stall: each `%` becomes its own lazy quantifier, so the work grows polynomially with the number of `%`s.

## Property-Based Test

```python
@given(names, names)
def test_wildcard_literal(wild, other):
    """CLAIM-1: non-wildcard characters are literal; never raises."""
    pat = imap4.wildcardToRegexp(wild, "/")
    assert pat.match(wild)
    if pat.match(other):
        assert other.upper().startswith(wild.upper())


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=1, max_value=12))
def test_list_does_not_hang(n):
    """CLAIM-2: LIST pattern matching completes in bounded time."""
    acct = _Account("u")
    acct.addMailbox("a" * 30)
    t = time.perf_counter()
    acct.listMailboxes("", "%" * n + "b")
    assert time.perf_counter() - t < 1.0
```

**Failing input**: `wild='['` (raises `re.PatternError`); `n=9` (more than 1 second; `n=10` takes about 7 seconds)

## Reproducing the Bug

```python
import time
from twisted.mail import imap4

print(imap4.wildcardToRegexp("a.b", "/").match("aXb"))

try:
    imap4.wildcardToRegexp("[", "/")
except Exception as e:
    print(type(e).__name__, e)

p = imap4.wildcardToRegexp("(a+)+b", "/")
t = time.perf_counter(); p.match("a" * 26); print(time.perf_counter() - t)

p = imap4.wildcardToRegexp("%" * 10 + "b", "/")
t = time.perf_counter(); p.match("a" * 30); print(time.perf_counter() - t)
```

## Why This Is A Bug

The `IMAP4Client.list` docstring (and RFC 3501 §6.3.8) names only `*` and `%` as wildcards, so every other character of a mailbox pattern is literal. Mailbox names often contain `.` (as in `INBOX.Sent`), `[`, `(` and `+`. Because these characters are not escaped:

- `.` acts as a wildcard, so the wrong mailboxes are listed;
- `[` and `(` make the server raise instead of answering;
- a client-chosen regex makes `LIST` take exponential time.

The `%` case shows that even a correct, well-formed pattern blows up. The match runs on the reactor thread, so one `LIST` command blocks every connection on the server.

## Fix

```diff
 def wildcardToRegexp(wildcard: str, delim: str | None = None) -> re.Pattern[str]:
-    wildcard = wildcard.replace("*", "(?:.*?)")
-    if delim is None:
-        wildcard = wildcard.replace("%", "(?:.*?)")
-    else:
-        wildcard = wildcard.replace("%", "(?:(?:[^%s])*?)" % re.escape(delim))
-    return re.compile(wildcard, re.I)
+    # Runs of wildcards are equivalent to a single one ('*' wins over '%').
+    wildcard = re.sub(r"[*%]+", lambda m: "*" if "*" in m.group() else "%", wildcard)
+    if delim is None:
+        percent = "(?:.*?)"
+    else:
+        percent = "(?:[^%s]*?)" % re.escape(delim)
+    pieces = []
+    for piece in re.split(r"([*%])", wildcard):
+        if piece == "*":
+            pieces.append("(?:.*?)")
+        elif piece == "%":
+            pieces.append(percent)
+        else:
+            pieces.append(re.escape(piece))
+    return re.compile("".join(pieces), re.I)
```

This patch removes the regex injection and the `%%%…` blow-up. A pattern that alternates wildcards and literals, such as `a%a%a%…`, can still backtrack polynomially. Fully bounding the cost needs a linear-time glob matcher, such as a greedy two-pointer or a DP match, instead of the backtracking `re` engine.

# Bug Report: twisted.mail.imap4.wildcardToRegexp compiles client-supplied LIST wildcards as raw regular expressions

**Target**: `twisted.mail.imap4.wildcardToRegexp` (via `MemoryAccountWithoutNamespaces.listMailboxes`, reached from `IMAP4Server` `LIST` / `LSUB`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`wildcardToRegexp` replaces `*` and `%` with regex fragments but never escapes the rest of the wildcard, and the result is used with `.match()` (no end anchor). Any authenticated IMAP client controls the wildcard. That causes three problems:

1. **Denial of service.** A wildcard such as `'%' * k + 'Z'` makes matching cost grow polynomially in `k`, roughly C(k+n, n) for a name of length n. An 81-byte wildcard costs 3.4 s against `INBOX`, and a few hundred bytes blocks the reactor for hours.
2. **Crash.** Wildcards such as `(`, `[`, `\`, `(?` or `\1` raise `re.error` inside the server.
3. **Wrong results.** Regex metacharacters are treated as operators: `A.B` lists `AXB`, and `$` lists nothing. Because matching is unanchored, `INBOX` also lists `INBOX.OLD`, and `%` lists `A/B` even though `%` must not cross the `/` hierarchy delimiter.

## Property-Based Test

```python
class Box:
    def __init__(self, name):
        self.name = name

class Acct(MemoryAccount):
    def _emptyMailbox(self, name, id):
        return Box(name)

name_chars = st.sampled_from("ABCXYZ.+()[]?^$|\\{}0123")
segment = st.text(name_chars, min_size=1, max_size=5)
names = st.lists(segment, min_size=1, max_size=3).map("/".join)

@settings(max_examples=500)
@given(st.lists(names, min_size=1, max_size=5), st.data())
def test_literal_wildcard_selects_exact_name(ns, data):
    """CLAIM-1: a wildcard without '*'/'%' lists exactly the mailbox of that name."""
    a = _make(ns)
    w = data.draw(st.one_of(st.sampled_from(ns), names))
    try:
        got = sorted(n for n, _ in a.listMailboxes("", w))
    except re.error as e:
        raise AssertionError(f"re.error for wildcard {w!r}: {e}")
    expected = sorted(n for n in a.mailboxes if n == w.upper())
    assert got == expected, (w, got, expected)

@settings(max_examples=300)
@given(st.lists(names, min_size=1, max_size=5), st.data())
def test_percent_does_not_cross_delimiter(ns, data):
    """CLAIM-1: 'P%' never returns a name with '/' after prefix P."""
    a = _make(ns)
    prefix = data.draw(st.text(st.sampled_from("ABCXYZ0123"), max_size=3))
    for n, _ in a.listMailboxes("", prefix + "%"):
        assert "/" not in n[len(prefix):], (prefix + "%", n)

def test_wildcard_cost_bounded():
    """CLAIM-2: matching cost does not explode with wildcard length."""
    code = ("from twisted.mail.imap4 import wildcardToRegexp;"
            "wildcardToRegexp('%' * 24 + 'X', '/').match('A' * 24)")
    subprocess.run([sys.executable, "-c", code], timeout=5, check=True)
```

**Failing input**: `ns=['['], w='['` (re.error); `ns=['$'], w='$'` (lists nothing); `ns=['0/0'], wildcard='%'` (returns `0/0`); `'%'*24+'X'` vs `'A'*24` (timeout)

## Reproducing the Bug

```python
import re, time
from twisted.mail.imap4 import MemoryAccount, wildcardToRegexp

class Acct(MemoryAccount):
    def _emptyMailbox(self, name, id):
        return object()

a = Acct("u")
for n in ["INBOX", "INBOX.OLD", "AXB", "A/B"]:
    a.addMailbox(n)

print([n for n, _ in a.listMailboxes("", "INBOX")])
print([n for n, _ in a.listMailboxes("", "A.B")])
print([n for n, _ in a.listMailboxes("", "%")])

try:
    a.listMailboxes("", "(")
except re.error as e:
    print("re.error:", e)

for k in (20, 40, 80):
    t = time.perf_counter()
    a.listMailboxes("", "%" * k + "Z")
    print(k, round(time.perf_counter() - t, 3))
```

Output:
```
['INBOX', 'INBOX.OLD']
['AXB']
['INBOX', 'INBOX.OLD', 'AXB', 'A/B']
re.error: missing ), unterminated subpattern at position 0
20 0.002
40 0.072
80 3.391
```

Over the network, an authenticated client sends `a1 LIST "" "%%%%…%Z"`. `IMAP4Server._listWork` passes that string straight to `account.listMailboxes`, which runs the match synchronously on the reactor thread.

## Why This Is A Bug

`IAccount.listMailboxes` (`twisted/mail/interfaces.py:982-986`) documents the wildcard as follows: "'*' matches any number of characters in a mailbox name, and '%' matches similarly, but will not match across hierarchical boundaries." No other character is special, so every other character must match itself and the wildcard must match the whole name. The wildcard comes straight from the network, so compiling it unescaped lets any logged-in user crash the command or stall the whole server process.

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
+        percent = "(?:[^%s]*?)" % re.escape(delim)
+    parts = []
+    for tok in re.split(r"([*%]+)", wildcard):
+        if not tok:
+            continue
+        if tok[0] in "*%":
+            # a run of wildcards is equivalent to a single one
+            parts.append("(?:.*?)" if "*" in tok else percent)
+        else:
+            parts.append(re.escape(tok))
+    return re.compile("".join(parts) + r"\Z", re.I | re.S)
```

With this patch the three wildcard properties pass, and `'%'*400+'Z'` against `INBOX` takes about 0.1 ms. Wildcards with many separated runs, such as `%a%a%a…`, can still backtrack polynomially. A fully robust fix would use a linear-time glob matcher instead of a backtracking regex.

# Bug Report: twisted.mail.imap4 parseIdList takes quadratic time in the number of sequence-set parts

**Target**: `twisted.mail.imap4.parseIdList` (via `MessageSet.add` / `MessageSet.extend`)
**Severity**: Medium
**Bug Type**: Logic (performance / denial of service)
**Date**: 2026-10-28

## Summary

`parseIdList` calls `MessageSet.add`/`extend` once for each comma-separated part. Each of those calls `clean()`, which re-sorts every range collected so far. Total cost is therefore O(n² log n) in the number of parts. A single 16 KB command line from a client blocks the server's reactor for about 1 s.

## Property-Based Test

```python
def _time_parse(n):
    s = b",".join(b"%d" % (2 * i + 1) for i in range(n))
    t = time.perf_counter()
    imap4.parseIdList(s)
    return time.perf_counter() - t

@settings(max_examples=5, deadline=None)
@given(st.integers(1500, 2500))
def test_parseidlist_linear(n):
    """CLAIM-5: parseIdList cost is linear in the number of parts."""
    small = min(_time_parse(n) for _ in range(2))
    big = min(_time_parse(2 * n) for _ in range(2))
    assert big / small < 3.0, (n, small, big)
```

**Failing input**: `n=1500` (0.18 s for 1,500 parts, 0.77 s for 3,000 parts: doubling the input took 4.2× as long)

## Reproducing the Bug

```python
import time
from twisted.mail.imap4 import IMAP4Server, parseIdList

for n in [2000, 4000, 8000]:
    s = b",".join(b"%d" % (2 * i + 1) for i in range(n))
    t = time.perf_counter()
    parseIdList(s)
    print(n, len(s), time.perf_counter() - t)

line = b",".join(b"%d" % (2 * i + 1) for i in range(3400)) + b" (FLAGS)"
t = time.perf_counter()
IMAP4Server().arg_seqset(line)
print(len(line), time.perf_counter() - t)
```

Output:

```
2000 9444 0.353
4000 19444 1.456
8000 42444 5.937
16452 1.0167
```

## Why This Is A Bug

Clients control the sequence sets that `parseIdList` parses:

- `arg_seqset` uses it for FETCH, STORE and COPY.
- `search_UID` and `_singleSearchStep` use it on every SEARCH term. In the manual-search path this happens once per message in the mailbox.

Parsing should take time proportional to the input. Instead, one line that fits under the default 16384-byte `MAX_LENGTH` blocks the single-threaded reactor for about a second. A client can pipeline such lines, or use them as SEARCH terms over a large mailbox, and stall the server for all other users. Merging the ranges once at the end gives the same `MessageSet`: 3,000 random sequence sets, with and without `lastMessageId`, produced identical results. The fixed version takes 0.0034 s at 8,000 parts, compared with 5.9 s before.

## Fix

```diff
--- a/src/twisted/mail/imap4.py
+++ b/src/twisted/mail/imap4.py
@@ def parseIdList(s, lastMessageId=None):
-    res = MessageSet()
+    key = functools.partial(_swap, that=MessageSet._infinity, ifIs=None)
+    ranges = []
     parts = s.split(b",")
     for p in parts:
@@
                 high = high or lastMessageId
                 low = low or lastMessageId
 
-                res.add(low, high)
+                ranges.append(tuple(sorted([low, high], key=key)))
             except ValueError:
                 raise IllegalIdentifierError(p)
@@
             except ValueError:
                 raise IllegalIdentifierError(p)
             else:
-                res.extend(p or lastMessageId)
-    return res
+                p = p or lastMessageId
+                ranges.append((p, p))
+    return MessageSet(ranges)
```

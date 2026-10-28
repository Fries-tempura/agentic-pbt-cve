# Bug Report: twisted.mail.imap4 MessageSet iteration/membership on an empty set raises IndexError

**Target**: `twisted.mail.imap4.MessageSet.__iter__`, `MessageSet.__contains__`
**Severity**: Low
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

`_noneInRanges` reads `self.ranges[-1][-1]`, which raises `IndexError` when the set has no ranges. `len(MessageSet())` returns `0`, but `list(MessageSet())` and `1 in MessageSet()` both crash.

## Property-Based Test

```python
@given(st.lists(st.tuples(st.integers(1, 200), st.integers(1, 200)), max_size=6),
       st.lists(st.tuples(st.integers(1, 200), st.integers(1, 200)), max_size=6))
def test_messageset_add_union(r1, r2):
    a, b = build(r1), build(r2)
    assert set(a + b) == set(a) | set(b)
```

**Failing input**: `r1=[], r2=[]`

## Reproducing the Bug

```python
from twisted.mail.imap4 import MessageSet

m = MessageSet()
assert len(m) == 0
list(m)   # IndexError: list index out of range
1 in m    # IndexError: list index out of range
```

## Why This Is A Bug

`MessageSet()` is a supported constructor; `parseIdList` uses it as its starting value. An empty set should iterate as empty and contain nothing, as `__len__` already implies, instead of failing with an internal `IndexError`.

## Fix

```diff
     def _noneInRanges(self):
-        return self.ranges[-1][-1] is None
+        return bool(self.ranges) and self.ranges[-1][-1] is None
```

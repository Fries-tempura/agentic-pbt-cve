# Bug Report: soupsieve.css_parser quadratic-time parsing of whitespace runs (ReDoS)

**Target**: `soupsieve.css_parser.CSSParser.selector_iter` (`RE_WS_END`)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`selector_iter` locates trailing whitespace with `RE_WS_END.search(pattern)`, where `RE_WS_END = {WSC}*$`. When a long run of whitespace or comments is followed by any other character, `search` retries at every start position inside the run, scanning to the end of the run each time. Parse time is O(n²) in the run length, even for valid selectors like `"a" + " " * n + "b"`.

## Property-Based Test

```python
@settings(max_examples=20, deadline=None, suppress_health_check=list(HealthCheck))
@given(ws=st.sampled_from([' ', '\t', '\n', '/**/']),
       tail=st.sampled_from(['b', '!', '>b', '', ')']),
       head=st.sampled_from(['a', '[x', ':is(a', 'div.c']))
def test_linear_time(ws, head, tail):
    """CLAIM-1: compile time is roughly linear in the length of a whitespace run."""
    n = 3000
    t1 = _time(head + ws * n + tail)
    t2 = _time(head + ws * (2 * n) + tail)
    assert t2 < 0.05 or t2 / max(t1, 1e-3) < 3.0, (t1, t2)
```

**Failing input**: `head='[x', ws=' ', tail='b'` (0.21 s → 0.85 s when the run doubles)

## Reproducing the Bug

```python
import time
import soupsieve as sv

for n in (4000, 8000, 16000):
    t = time.perf_counter()
    sv.compile("a" + " " * n + "b")
    print(n, round(time.perf_counter() - t, 2))
```

Output: `4000 0.39`, `8000 1.54`, `16000 6.1` — time quadruples each time the input doubles. The same holds for `/**/` runs, tabs, newlines, and for invalid selectors (`"a" + " " * n + "!"`), which burn the CPU time before raising.

## Why This Is A Bug

Soup Sieve compiles selectors that frequently come from untrusted sources (scrapers, user-configurable filters). A ~16 KB string of spaces costs 6 s of CPU; a 64 KB one costs ~100 s. A tokenizer has no reason to be super-linear, and the cost here comes only from a pre-scan for trailing whitespace.

## Fix

Instead of searching the whole string for trailing whitespace, stop the token loop once the remainder is only whitespace/comments. Anchored `match` from the current index costs only the length of the run it is standing on, which the next token consumes anyway, so the total stays linear. Parse results are identical on the samples checked.

```diff
--- a/soupsieve/css_parser.py
+++ b/soupsieve/css_parser.py
@@ def selector_iter(self, pattern: str) -> Iterator[tuple[str, Match[str]]]:
         # Ignore whitespace and comments at start and end of pattern
         m = RE_WS_BEGIN.search(pattern)
         index = m.end(0) if m else 0
-        m = RE_WS_END.search(pattern)
-        end = (m.start(0) - 1) if m else (len(pattern) - 1)
+        length = len(pattern)
 
         if self.debug:  # pragma: no cover
             print(f'## PARSING: {pattern!r}')
-        while index <= end:
+        while index < length and not RE_WS_END.match(pattern, index):
             m = None
```

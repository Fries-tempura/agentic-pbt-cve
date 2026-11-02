# Bug Report: soupsieve.css_parser RecursionError on nested pseudo-classes far below the selector limit

**Target**: `soupsieve.css_parser.CSSParser.parse_selectors` (via `soupsieve.compile` / `select`)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

`parse_selectors` recurses once for each nested `:is(` / `:not(` / `:where(` / `:has(`. At the default
recursion limit of 1000, a nesting depth of 331 is enough to raise `RecursionError`. That selector's
count (~332) is far below the documented `SELECTOR_LIMIT` of 8192, which the code describes as a
"pseudo-class nesting limit". So the guard meant to reject oversized selectors never runs, and an
untrusted selector crashes the caller with an undocumented exception.

## Property-Based Test

```python
@settings(max_examples=60, deadline=None)
@given(depth=st.integers(min_value=1, max_value=2000),
       pseudo=st.sampled_from([':is(', ':not(', ':where(', ':has(> ']))
def test_nesting_below_limit_compiles(depth, pseudo):
    """CLAIM-1: nested selectors with count well below SELECTOR_LIMIT never raise RecursionError."""
    sel = pseudo * depth + 'a' + ')' * depth
    sv.purge()
    try:
        sv.compile(sel)
    except (SelectorSyntaxError, ValueError):
        pass  # documented failure modes
```

**Failing input**: `depth=331, pseudo=':is('` (all four pseudo-classes fail)

## Reproducing the Bug

```python
import soupsieve as sv

sv.compile(':is(' * 331 + 'a' + ')' * 331)
```

```
RecursionError: maximum recursion depth exceeded
```

## Why This Is A Bug

`check_count` raises `ValueError('Selector exceeds pseudo-class nesting limit of 8192')`, and
`docs/src/markdown/api.md` says selectors are capped at ~8192 "to prevent cases where impractical,
massive selectors". The intended response to an oversized or deeply nested selector is that clean
`ValueError`. Instead, a selector at about 4% of the limit escapes as a `RecursionError`, an
interpreter-level failure that callers do not expect from `compile` or `select`. The pattern is a
few kilobytes of user-controllable text, so any service that applies user-supplied selectors with
BeautifulSoup/soupsieve can be crashed this way.

## Fix

Track nesting depth separately and reject it with the documented error before Python's stack runs out:

```diff
@@ class CSSParser:
     def __init__(self, selector, custom=None, flags=0) -> None:
         ...
         self.count = 0
+        self.depth = 0
 
@@ def parse_selectors(self, iselector, index=0, flags=0):
+        self.depth += 1
+        if self.depth > NESTING_LIMIT:  # e.g. 256
+            raise SelectorSyntaxError(
+                f'Selector exceeds pseudo-class nesting limit of {NESTING_LIMIT}', self.pattern, index
+            )
+        try:
+            return self._parse_selectors(iselector, index, flags)
+        finally:
+            self.depth -= 1
```

The parser could also be rewritten iteratively with an explicit stack. Nested custom selectors,
which construct a new `CSSParser` for each level, need the depth passed through to them too.

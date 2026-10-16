# Bug Report: soupsieve.css_parser Deeply nested pseudo-classes crash with RecursionError, bypassing the nesting limit

**Target**: `soupsieve.css_parser.CSSParser.parse_selectors` (reachable via `soupsieve.compile` / `select` / `match`)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-05

## Summary

`CSSParser` has a nesting guard (`SELECTOR_LIMIT = 8192`, `check_count()` raising `ValueError("Selector exceeds pseudo-class nesting limit ...")`). But parsing is recursive (`parse_selectors` → `parse_pseudo_class` → `parse_pseudo_open` → `parse_selectors`), so with the default recursion limit of 1000, a selector nested only ~331 levels deep (e.g. `:is(:is(...a...))`) hits an uncaught `RecursionError` long before the guard can trigger. Any app that compiles untrusted selectors gets an unhandled crash instead of the documented `SelectorSyntaxError`/`ValueError`.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from soupsieve import css_parser as cp
from soupsieve.util import SelectorSyntaxError

SIMPLE = st.sampled_from(['div', 'p', '.a', '#b', '[x]', '[x="y"]', ':first-child', '*', ':not(p)'])
WRAP = st.sampled_from([':is({})', ':not({})', ':where({})', ':has(> {})', ':nth-child(2n+1 of {})'])


@given(st.integers(1, 3000).flatmap(lambda n: st.lists(WRAP, min_size=n, max_size=n)), SIMPLE)
@settings(max_examples=200, deadline=None)
def test_nested_selectors_only_raise_documented_errors(wraps, inner):
    s = inner
    for w in wraps:
        s = w.format(s)
    try:
        cp.CSSParser(s).process_selectors()
    except (SelectorSyntaxError, ValueError):
        pass
```

**Failing input**: any wrap list of length ≥ ~331, e.g. `':is(' * 331 + 'a' + ')' * 331`

## Reproducing the Bug

```python
import soupsieve as sv

sv.compile(':is(' * 331 + 'a' + ')' * 331)
```

Output (Python 3.14.7, recursion limit 1000):

```
RecursionError: maximum recursion depth exceeded
```

## Why This Is A Bug

The parser clearly means to bound nesting and reject overly deep selectors with a controlled `ValueError` (see `SELECTOR_LIMIT` and `check_count`). That limit counts tokens, though, and recursion depth is what actually overflows the interpreter stack. Selectors of just ~1000 characters (well under the 8192 token budget) cause an unhandled `RecursionError`. When selectors come from untrusted sources (scrapers, user-provided queries), that is a crash/DoS vector. The matcher (`css_match`) also recurses over nested selector lists, so depths that parse successfully (~250–330) can still overflow during `select()`.

## Fix

Track the actual nesting depth and reject it with a controlled error well below the interpreter recursion limit:

```diff
--- a/soupsieve/css_parser.py
+++ b/soupsieve/css_parser.py
@@
 SELECTOR_LIMIT = 8192
+# Maximum depth of nested selector lists (`:is(:not(...))`, etc.)
+NESTING_LIMIT = 100
@@ class CSSParser:
         self.custom = {} if custom is None else custom
         self.count = 0
+        self.depth = 0
@@ def parse_selectors(
-        # The algorithm for relative selectors require an initial selector in the selector list
+        self.depth += 1
+        if self.depth > NESTING_LIMIT:
+            raise SelectorSyntaxError(
+                f'Selector exceeds pseudo-class nesting depth limit of {NESTING_LIMIT}',
+                self.pattern,
+                index
+            )
+        try:
+            return self._parse_selectors(iselector, index, flags)
+        finally:
+            self.depth -= 1
```

(where the current body of `parse_selectors` is moved to `_parse_selectors`). Custom selectors compiled through `parse_pseudo_class_custom` create a fresh `CSSParser`, so the depth should also be passed into that nested parser to prevent recursion through chains of custom selectors.

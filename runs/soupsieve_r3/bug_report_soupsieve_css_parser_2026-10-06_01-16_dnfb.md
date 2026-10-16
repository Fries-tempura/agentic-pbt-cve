# Bug Report: soupsieve.css_parser Deeply nested pseudo-classes crash with RecursionError

**Target**: `soupsieve.css_parser.CSSParser.parse_selectors`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-06

## Summary

The parser has a guard (`SELECTOR_LIMIT = 8192`, `check_count`) whose error message says "Selector exceeds pseudo-class nesting limit". But it counts tokens, not nesting depth. Each nested `:is(`/`:not(`/`:has(`/`:where(` adds about three recursive Python frames (`parse_selectors` → `parse_pseudo_class` → `parse_pseudo_open`). So roughly 330 levels of nesting hit Python's recursion limit long before the guard fires. `sv.compile` then raises an uncaught `RecursionError` instead of `SelectorSyntaxError`/`ValueError`. A short (~2 KB) untrusted selector can crash any application that catches only soupsieve's documented errors.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
import soupsieve as sv
from soupsieve.util import SelectorSyntaxError

@settings(max_examples=50, deadline=None)
@given(st.integers(1, 3000), st.sampled_from([':is(', ':not(', ':has(> ', ':where(', ':nth-child(1 of ']))
def test_deep_nesting_no_crash(n, p):
    sel = 'div' + p * n + 'div' + ')' * n
    try:
        sv.compile(sel)
    except (SelectorSyntaxError, ValueError):
        pass
```

**Failing input**: `n=400, p=':is('` (any n >= ~330 with the default recursion limit of 1000)

## Reproducing the Bug

```python
import soupsieve as sv

n = 400
sv.compile('div' + ':is(' * n + 'div' + ')' * n)
```

Output: `RecursionError: maximum recursion depth exceeded`

## Why This Is A Bug

The code clearly means to cap nesting and report it as a controlled error (`ValueError('Selector exceeds pseudo-class nesting limit of 8192')`). The cap can never be reached through nesting, because the interpreter's recursion limit is hit first. That gives an unhandled `RecursionError`, a denial-of-service vector for services that compile user-supplied selectors.

## Fix

Track the real nesting depth and fail with `SelectorSyntaxError` before the Python stack runs out:

```diff
--- a/soupsieve/css_parser.py
+++ b/soupsieve/css_parser.py
@@
 SELECTOR_LIMIT = 8192
+NESTING_LIMIT = 100
@@ class CSSParser:
         self.custom = {} if custom is None else custom
         self.count = 0
+        self.depth = 0
@@ def parse_selectors(
         rel_type = ":" + WS_COMBINATOR
         count = self.count
+
+        self.depth += 1
+        if self.depth > NESTING_LIMIT:
+            raise SelectorSyntaxError(
+                f'Selector exceeds pseudo-class nesting limit of {NESTING_LIMIT}',
+                self.pattern,
+                index
+            )
+        try:
+            return self._parse_selectors(iselector, index, flags, sel, selectors, has_selector, closed,
+                                         relations, rel_type, count)
+        finally:
+            self.depth -= 1
```

(Or more simply: wrap the body of `parse_selectors` in `try/finally` that increments/decrements `self.depth` and checks it against a limit well below `sys.getrecursionlimit() // 3`.)

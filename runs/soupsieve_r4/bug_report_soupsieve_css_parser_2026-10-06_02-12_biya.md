# Bug Report: soupsieve.css_parser Deeply nested pseudo-classes crash compile with RecursionError

**Target**: `soupsieve.css_parser.CSSParser.parse_selectors` (via `soupsieve.compile` / `select`)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-06

## Summary

A selector with roughly 340 nested `:is(` / `:not(` / `:has(` / `:where(` / `:nth-child(... of` groups makes `soupsieve.compile` raise an unhandled `RecursionError`. The `SELECTOR_LIMIT` guard (8192, error text "Selector exceeds pseudo-class nesting limit") was added to stop oversized selectors, but it counts selectors in total and never limits nesting depth, so Python's recursion limit is reached first. Such a selector is only about 1.7 KB.

## Property-Based Test

```python
@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=1, max_value=3000), st.sampled_from([':is(', ':not(', ':where(', ':has(']))
def test_nesting_does_not_recurse_out(depth, p):
    s = p * depth + 'a' + ')' * depth
    try:
        sv.compile(s)
    except (ValueError, SelectorSyntaxError):
        pass
```

**Failing input**: depth ≈ 340 for `:is(` (the default recursion limit is 1000). It also fails for `:not(`, `:where(`, `:has(` and `a:nth-child(2n of ...)`.

## Reproducing the Bug

```python
import soupsieve as sv

sv.compile(':is(' * 400 + 'a' + ')' * 400)
```

```
RecursionError: maximum recursion depth exceeded
```

## Why This Is A Bug

`compile` is documented to report bad selectors with `SelectorSyntaxError`. The library also sets an explicit limit, raising `ValueError`, so that oversized selectors are rejected cleanly. Here a short selector skips both checks and fails with `RecursionError`. Applications that pass user-supplied selectors to soupsieve normally catch `SelectorSyntaxError`/`ValueError`, so this input crashes them. That makes it a denial-of-service risk. Each pseudo-class level uses about three Python stack frames (`parse_selectors` → `parse_pseudo_class` → `parse_pseudo_open`), so the selector-count limit can never be reached before the stack runs out.

## Fix

Track nesting depth in the parser and reject it with a clear error before the interpreter limit is reached:

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
-        try:
+        self.depth += 1
+        if self.depth > NESTING_LIMIT:
+            raise SelectorSyntaxError(
+                f'Selector exceeds pseudo-class nesting depth of {NESTING_LIMIT}', self.pattern, index
+            )
+        try:
             while True:
@@
         except StopIteration:
             pass
+        finally:
+            self.depth -= 1
```

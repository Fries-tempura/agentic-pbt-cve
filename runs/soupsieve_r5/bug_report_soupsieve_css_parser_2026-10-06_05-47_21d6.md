# Bug Report: soupsieve.css_parser Nesting limit ineffective, deeply nested pseudo-classes raise RecursionError

**Target**: `soupsieve.css_parser.CSSParser.parse_selectors` (via `soupsieve.compile` / `select`)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-06

## Summary

The parser has a "pseudo-class nesting limit" (`SELECTOR_LIMIT = 8192`, enforced by `check_count()` with a `ValueError`). But each nested `:is(`/`:not(`/`:has(`/`:where(` recurses through `parse_selectors -> parse_pseudo_class -> parse_pseudo_open`. That uses 3 Python frames per level, so with the default recursion limit the parser hits an uncaught `RecursionError` at about 331 levels. The token count at that point is only about 331, far below the limit. The guard never fires for deep nesting, and attacker-controlled selectors crash the parser with an undocumented exception instead of `SelectorSyntaxError`/`ValueError`.

## Property-Based Test

```python
import pytest
import soupsieve as sv
from soupsieve.util import SelectorSyntaxError

@pytest.mark.parametrize('name', [':is', ':not', ':has', ':where'])
@pytest.mark.parametrize('depth', [100, 200, 500, 1000, 2000])
def test_deep_nesting(name, depth):
    s = f'{name}(' * depth + 'div' + ')' * depth
    try:
        sv.compile(s)
    except (SelectorSyntaxError, ValueError):
        pass
```

**Failing input**: `':is(' * 331 + 'div' + ')' * 331` (the same happens with `:not`, `:has` and `:where`)

## Reproducing the Bug

```python
import soupsieve as sv
from soupsieve import css_parser as cp

d = 331
p = cp.CSSParser(':is(' * (d - 1) + 'div' + ')' * (d - 1))
p.process_selectors()
print(p.count, cp.SELECTOR_LIMIT)  # 331 8192

sv.compile(':is(' * d + 'div' + ')' * d)  # RecursionError: maximum recursion depth exceeded
```

## Why This Is A Bug

`SELECTOR_LIMIT`/`check_count` exist to turn excessive pseudo-class nesting into a controlled `ValueError` ("Selector exceeds pseudo-class nesting limit of 8192"). Python's recursion limit (about 331 nesting levels) is always reached long before the 8192 count limit, so the guard can never catch deep nesting. Applications that compile untrusted selectors and handle `SelectorSyntaxError`/`ValueError` will instead get an unhandled `RecursionError` (DoS). Under a raised recursion limit or in threads with small stacks, this can also become a hard interpreter crash.

## Fix

Track the actual nesting depth and fail cleanly well below the Python recursion limit:

```diff
@@ class CSSParser:
     def __init__(...):
         ...
         self.count = 0
+        self.depth = 0
@@ def parse_selectors(self, iselector, index=0, flags=0):
+        self.depth += 1
+        try:
+            if self.depth > NESTING_LIMIT:  # e.g. NESTING_LIMIT = 100
+                raise SelectorSyntaxError(
+                    f'Selector exceeds pseudo-class nesting depth limit of {NESTING_LIMIT}',
+                    self.pattern,
+                    index
+                )
+            return self._parse_selectors(iselector, index, flags)
+        finally:
+            self.depth -= 1
```

(Equivalently, catch `RecursionError` in `process_selectors` and re-raise it as `SelectorSyntaxError`. The matcher in `css_match` should get the same treatment for deep selectors that do compile.)

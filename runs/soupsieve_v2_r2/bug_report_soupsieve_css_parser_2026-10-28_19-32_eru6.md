# Bug Report: soupsieve.css_parser nested pseudo-classes raise RecursionError instead of the documented nesting-limit error

**Target**: `soupsieve.css_parser.CSSParser.parse_selectors`
**Severity**: Low
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

The parser has an explicit guard, `check_count`, that raises `ValueError("Selector exceeds pseudo-class nesting limit of 8192")`. But each nested `:is(`/`:not(`/`:where(`/`:has(` recurses through `parse_selectors → parse_pseudo_class → parse_pseudo_open → parse_selectors`, so Python's recursion limit is reached at about 350 levels of nesting. That is far below the 8192 limit, so for nesting the guard never fires and callers get an undocumented `RecursionError`.

## Property-Based Test

```python
@settings(max_examples=60, deadline=None)
@given(depth=st.integers(1, 2000),
       pseudo=st.sampled_from([':is(', ':not(', ':where(', ':has(> ']),
       closed=st.booleans())
def test_only_documented_exceptions(depth, pseudo, closed):
    """CLAIM-2: compile raises only SelectorSyntaxError/ValueError/NotImplementedError."""
    p = pseudo * depth + 'a' + (')' * depth if closed else '')
    cp._purge_cache()
    try:
        sv.compile(p)
    except ALLOWED:
        pass
```

**Failing input**: `depth=903, pseudo=':not(', closed=True` (also fails with `':is('`, `closed=False`)

## Reproducing the Bug

```python
import soupsieve as sv

sv.compile(":not(" * 400 + "a" + ")" * 400)
```

Result: `RecursionError: maximum recursion depth exceeded`. Depth 325 works, depth 350 fails under the default recursion limit of 1000.

## Why This Is A Bug

`SELECTOR_LIMIT` and `check_count` exist so that selectors that are nested too deeply fail with a clean `ValueError`. Nesting depth is the one case where the guard never gets to run. Applications that catch `SelectorSyntaxError`/`ValueError` around `compile` to reject bad user selectors will instead see a `RecursionError` they don't expect.

## Fix

Track nesting depth separately, increasing it on each `parse_selectors` call made with `FLG_OPEN`, and raise `ValueError`/`SelectorSyntaxError` once it passes a depth that is safe within the recursion limit (for example 256). Another option is to catch `RecursionError` in `process_selectors` and re-raise it as `ValueError(f'Selector exceeds pseudo-class nesting limit')`.

```diff
--- a/soupsieve/css_parser.py
+++ b/soupsieve/css_parser.py
@@ def process_selectors(self, index: int = 0, flags: int = 0) -> ct.SelectorList:
         """Process selectors."""
 
-        return self.parse_selectors(self.selector_iter(self.pattern), index, flags)
+        try:
+            return self.parse_selectors(self.selector_iter(self.pattern), index, flags)
+        except RecursionError:
+            raise ValueError('Selector exceeds pseudo-class nesting limit') from None
```

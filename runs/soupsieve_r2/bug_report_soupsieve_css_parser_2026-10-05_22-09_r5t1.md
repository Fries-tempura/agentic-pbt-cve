# Bug Report: soupsieve.css_parser Deeply nested pseudo-classes raise RecursionError before the nesting limit

**Target**: `soupsieve.css_parser.CSSParser.parse_selectors` (`SELECTOR_LIMIT`, `check_count`)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-05

## Summary

The parser enforces a "pseudo-class nesting limit" of `SELECTOR_LIMIT = 8192` and should raise a clean `ValueError` when that limit is exceeded. In practice, a selector nested only about 400 levels deep (roughly 2 KB of text) crashes with an uncaught `RecursionError` first. The recursion goes `parse_selectors -> parse_pseudo_class -> parse_pseudo_open -> parse_selectors`, so the guard is never reached.

## Property-Based Test

```python
@settings(max_examples=50, deadline=None)
@given(st.integers(1, 2000), st.sampled_from([':is(', ':not(', ':has(', ':where(']))
def test_nesting_raises_only_documented_errors(n, p):
    try:
        cp.CSSParser(p * n + 'a' + ')' * n).process_selectors()
    except (SelectorSyntaxError, ValueError):
        pass
```

**Failing input**: `n≈400, p=':is('` (fails for every n above about 330 with the default recursion limit)

## Reproducing the Bug

```python
import soupsieve as sv

sv.compile(':is(' * 400 + 'a' + ')' * 400)  # RecursionError
```

## Why This Is A Bug

The code clearly intends to bound nesting: `check_count` raises `ValueError('Selector exceeds pseudo-class nesting limit of 8192')`. That limit can't be reached, because Python's recursion limit is hit at roughly 1/20th of the advertised depth. Any application that compiles untrusted selectors and catches `SelectorSyntaxError`/`ValueError` will instead get an unexpected `RecursionError`, which is a denial-of-service vector.

## Fix

Track nesting depth separately from the token count. Increment it when entering `parse_pseudo_open`, `parse_pseudo_nth` (`of S`) and the `PSEUDO_COMPLEX_NO_MATCH` branch, and decrement it on exit. Raise `SelectorSyntaxError`/`ValueError` once the depth goes over a limit that stays safely under `sys.getrecursionlimit()` (e.g. 100–200). Alternatively, convert `parse_selectors` to an explicit-stack iterative parser.

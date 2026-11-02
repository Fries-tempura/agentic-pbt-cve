# Bug Report: soupsieve.css_parser RecursionError on moderately nested pseudo-classes

**Target**: `soupsieve.css_parser.CSSParser.parse_selectors`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

Each nested `:is(`/`:not(`/`:has(`/`:where(` recurses into `parse_selectors` through several stack frames. About 400 levels of nesting are enough to hit Python's recursion limit and raise `RecursionError`. The module's own guard (`SELECTOR_LIMIT = 8192`, which raises `ValueError('Selector exceeds pseudo-class nesting limit ...')`) never gets a chance to fire.

## Property-Based Test

```python
@given(st.integers(min_value=1, max_value=2000))
@settings(max_examples=50, deadline=None)
def test_nesting_no_recursion_error(d):
    """CLAIM-4: deep :is() nesting raises only documented errors."""
    try:
        cp.CSSParser(':is(' * d + 'a' + ')' * d).process_selectors()
    except (ValueError, SelectorSyntaxError):
        pass
```

**Failing input**: `d=738` (manually: `d=400` already fails; `d=200` works)

## Reproducing the Bug

```python
import soupsieve as sv
sv.compile(':is(' * 400 + 'a' + ')' * 400)
```

## Why This Is A Bug

The parser documents its own nesting limit: 8192, enforced with a `ValueError` (`check_count`). A selector with 801 tokens is far below that limit, yet it crashes with `RecursionError`, which callers have no reason to expect and which can leave the interpreter's stack in a bad state. Untrusted selectors can trigger it with a few kilobytes of input.

## Fix

Bound the nesting depth explicitly and raise the documented error before Python's stack runs out. For example, track a `depth` counter in `parse_selectors` (increment on entry, decrement in `finally`) and raise `SelectorSyntaxError`/`ValueError` once it passes a safe value such as 100–200. The longer-term alternative is to rewrite the nested parse iteratively with an explicit stack.

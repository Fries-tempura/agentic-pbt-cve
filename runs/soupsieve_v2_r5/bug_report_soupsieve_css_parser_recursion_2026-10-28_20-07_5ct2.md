# Bug Report: soupsieve.css_parser RecursionError on long descendant chains

**Target**: `soupsieve.css_parser._Selector.freeze`
**Severity**: Low
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

A selector of about 600 compound selectors joined by descendant combinators (`a a a …`) raises `RecursionError`. This is far below the parser's own `SELECTOR_LIMIT` of 8192, which is supposed to reject oversized selectors with a `ValueError`.

## Property-Based Test

This was found by `test_linear_cost` (CLAIM-1/CLAIM-5) with `unit='a '`, i.e. `'a ' * 4000`.

## Reproducing the Bug

```python
import soupsieve as sv
sv.compile(' '.join(['a'] * 600))
```

`RecursionError: maximum recursion depth exceeded`. 400 parts compile fine.

## Why This Is A Bug

The parser has an explicit guard (`check_count`, limit 8192) meant to reject oversized selectors with a clear error. Below that limit, `_Selector.freeze` → `_freeze_relations` recurses once per combinator, so it overflows the Python stack first. The same behaviour is present in the released 2.9 wheel.

## Fix

Freeze the relation chain iteratively instead of recursively. A simpler option is to bound the number of combinators by a limit well under the recursion limit and raise `SelectorSyntaxError`/`ValueError` above it.

# Bug Report: configobj.validate.is_float Accepts NaN Regardless of min/max Bounds

**Target**: `configobj.validate.is_float`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-03

## Summary

`is_float(value, min, max)` claims to check "that it is between bounds", but the bounds are
tested with `value < min_val` / `value > max_val`. Both comparisons are `False` for NaN, so
`float('nan')` — and the string `'nan'`, which is exactly how it would appear in a config
file — passes *any* bounded float check.

## Property-Based Test

```python
@given(
    st.floats(allow_infinity=True, allow_nan=True),
    st.floats(allow_nan=False, allow_infinity=False),
    st.floats(allow_nan=False, allow_infinity=False),
)
def test_is_float_result_within_bounds(value, lo, hi):
    """is_float checks 'that it is between bounds' -- so a returned value must be."""
    assume(lo <= hi)
    try:
        result = is_float(value, lo, hi)
    except ValidateError:
        return
    assert lo <= result <= hi
```

**Failing input**: `value=nan, lo=0.0, hi=0.0`

## Reproducing the Bug

```python
from configobj.validate import Validator

v = Validator()
result = v.check('float(0, 1)', 'nan')
assert 0 <= result <= 1, result
```

## Why This Is A Bug

`is_float`'s docstring says the check tests "that a given value is a float ... and
optionally - that it is between bounds", and the module docstring advertises
`float(3, 9)` as "any value from 3 to 9". A validator whose entire purpose is to reject
out-of-range values returns NaN for `float(0, 1)`, `float(min=0)` and `float(max=1)` alike.

The input is realistic: `float('nan')` is the standard Python parse of the literal string
`nan`, so a config line such as `ratio = nan` validated against `ratio = float(0, 1)` is
silently accepted and the NaN propagates into the application. The same applies to
`is_float_list` and to `mixed_list('float', ...)`, which delegate to `is_float`.

Infinities behave correctly (`inf > max` is `True`), so NaN is the only leak.

The bug is in validate.py:883-886:

```python
if (min_val is not None) and (value < min_val):
    raise VdtValueTooSmallError(value)
if (max_val is not None) and (value > max_val):
    raise VdtValueTooBigError(value)
```

## Fix

Invert the comparisons so an unordered (NaN) value fails the bound rather than passing it:

```diff
--- a/src/configobj/validate.py
+++ b/src/configobj/validate.py
@@ -880,9 +880,9 @@ def is_float(value, min=None, max=None):
         try:
             value = float(value)
         except ValueError:
             raise VdtTypeError(value)
-    if (min_val is not None) and (value < min_val):
+    if (min_val is not None) and not (value >= min_val):
         raise VdtValueTooSmallError(value)
-    if (max_val is not None) and (value > max_val):
+    if (max_val is not None) and not (value <= max_val):
         raise VdtValueTooBigError(value)
     return value
```

Verified: with this patch `float(0, 1)`, `float(min=0)` and `float(max=1)` all reject
`'nan'`, and `is_float`'s 9 doctest examples still pass.

Note this only rejects NaN when a bound is actually given; an unbounded `float` check still
accepts NaN. If NaN should never validate, add an explicit
`if value != value: raise VdtTypeError(value)` after the conversion instead.

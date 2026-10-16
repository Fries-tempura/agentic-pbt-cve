# Bug Report: configobj.validate is_float raises OverflowError instead of a ValidateError for large ints

**Target**: `configobj.validate.is_float` (the `float` check)
**Severity**: Low
**Bug Type**: Crash
**Date**: 2026-10-05

## Summary

The `float` check documents that "an integer will be accepted", and `Validator.check` documents that a failing check "raises a `ValidateError` subclass". Passing an `int` larger than the maximum double (about 1.8e308) instead raises a bare `OverflowError` from `float(value)`. The function only catches `ValueError`, so this error escapes.

## Property-Based Test

```python
from hypothesis import given, strategies as st
from configobj.validate import Validator, ValidateError

@given(st.integers(min_value=-(10**400), max_value=10**400))
def test_float_accepts_ints(x):
    try:
        Validator().check("float", x)
    except ValidateError:
        pass
```

**Failing input**: `x = 10**309` (Hypothesis reported a ~309-digit integer)

## Reproducing the Bug

```python
from configobj.validate import Validator

Validator().check("float", 10**309)
```

```
OverflowError: int too large to convert to float
```

## Why This Is A Bug

The `Validator.check` contract says that a check failure is reported as a `ValidateError` subclass. ConfigObj's `validate()` relies on this: it catches `validator.baseErrorClass` (`ValidateError`) to record failures. An `OverflowError` therefore escapes and aborts validation of the whole config, instead of being reported as a bad value. The string form `'1' + '0'*309` does not hit this, because `float()` returns `inf` for it, so the two input forms behave inconsistently. Impact is limited because config values are normally strings.

## Fix

```diff
--- a/src/configobj/validate.py
+++ b/src/configobj/validate.py
@@ -878,7 +878,7 @@ def is_float(value, min=None, max=None):
         # if it's a string - does it represent a float ?
         try:
             value = float(value)
-        except ValueError:
+        except (ValueError, OverflowError):
             raise VdtTypeError(value)
     if (min_val is not None) and (value < min_val):
         raise VdtValueTooSmallError(value)
```

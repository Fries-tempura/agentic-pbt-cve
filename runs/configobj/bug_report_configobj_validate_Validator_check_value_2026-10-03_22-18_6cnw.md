# Bug Report: configobj.validate.Validator Raises Bare TypeError Instead of VdtParamError on Bad Check Arguments

**Target**: `configobj.validate.Validator._check_value`
**Severity**: Low
**Bug Type**: Contract
**Date**: 2026-10-03

## Summary

The module docstring promises "A badly formatted set of arguments will raise a
``VdtParamError``." When a check string supplies the wrong *number* of positional arguments
or an unknown keyword argument, the arguments are splatted straight into the check function
and Python's own `TypeError` escapes instead — including out of `ConfigObj.validate()`,
which only catches `ValidateError`.

## Property-Based Test

```python
@given(st.lists(st.integers(min_value=0, max_value=100), min_size=3, max_size=6))
def test_bad_arity_raises_vdt_param_error(args):
    """'A badly formatted set of arguments will raise a VdtParamError.'"""
    v = Validator()
    check = 'integer(%s)' % ', '.join(str(a) for a in args)
    try:
        v.check(check, '5')
    except (ValidateError, VdtParamError):
        pass
```

**Failing input**: `args=[0, 0, 0]` (i.e. the check string `integer(0, 0, 0)`)

## Reproducing the Bug

```python
from configobj import ConfigObj
from configobj.validate import Validator, ValidateError, VdtParamError

for spec in ('integer(1, 2, 3)', 'integer(bogus=1)'):
    try:
        ConfigObj({'x': '5'}, configspec=['x = ' + spec]).validate(Validator())
    except (ValidateError, VdtParamError):
        pass
    except TypeError as e:
        print(spec, '->', type(e).__name__, e)
```

Output:

```
integer(1, 2, 3) -> TypeError is_integer() takes from 1 to 3 positional arguments but 4 were given
integer(bogus=1) -> TypeError is_integer() got an unexpected keyword argument 'bogus'
```

## Why This Is A Bug

The module docstring (validate.py:126) states the contract: a badly formatted set of
arguments raises `VdtParamError`. `_is_num_param` honours it for *unparsable* values
(`integer(min=a)` → `VdtParamError`), but arity and keyword-name mistakes bypass that path
entirely — `_check_value` (validate.py:650-656) calls `fun(value, *fun_args, **fun_kwargs)`
with no guard.

The practical effect is in `ConfigObj.validate`, which wraps the call in
`except validator.baseErrorClass` (i.e. `ValidateError`). A typo in a configspec therefore
surfaces as an opaque `TypeError: is_integer() takes from 1 to 3 positional arguments but 4
were given` naming an internal function, rather than the documented
`VdtParamError: passed an incorrect value ... for parameter ...` that names the offending
check. Callers written against the documented contract do not catch it.

## Fix

Validate the call signature before invoking the check function:

```diff
--- a/src/configobj/validate.py
+++ b/src/configobj/validate.py
@@ -161,6 +161,7 @@ __all__ = (
 )


+import inspect
 import re
 import sys
 from pprint import pprint
@@ -650,8 +651,12 @@ class Validator(object):
     def _check_value(self, value, fun_name, fun_args, fun_kwargs):
         try:
             fun = self.functions[fun_name]
         except KeyError:
             raise VdtUnknownCheckError(fun_name)
         else:
+            try:
+                inspect.signature(fun).bind(value, *fun_args, **fun_kwargs)
+            except TypeError as e:
+                raise VdtParamError(fun_name, e)
             return fun(value, *fun_args, **fun_kwargs)
```

Binding the signature separately (rather than catching `TypeError` around the call) avoids
swallowing a genuine `TypeError` raised from *inside* a check function.

Verified: with this patch both spellings above raise `VdtParamError`, and the module's full
doctest suite (198 examples) still passes.

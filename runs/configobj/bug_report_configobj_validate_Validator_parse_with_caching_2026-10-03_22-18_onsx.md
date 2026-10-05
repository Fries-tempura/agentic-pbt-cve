# Bug Report: configobj.validate.Validator Cached `list(...)` Default Is Shared Across Calls

**Target**: `configobj.validate.Validator._parse_with_caching`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-03

## Summary

`Validator` caches parsed check strings and deliberately copies `fun_args` and `fun_kwargs`
"to work with *copies* of the data rather than the original (which are mutable of course)" —
but it never copies `default`. When the default is a list (`default=list(...)`), every call
returns the *same* list object, so mutating one result silently corrupts the validator's cache
and every other value that was filled in from that default.

## Property-Based Test

```python
@given(st.lists(
    st.text(alphabet=string.ascii_letters + string.digits, min_size=1, max_size=5),
    min_size=1, max_size=4))
def test_default_list_is_not_shared_between_calls(items):
    """Validator caches parsed checks but documents working on *copies*
    (see _parse_with_caching) -- a list default must not leak between calls."""
    v = Validator()
    check = 'pass(default=list(%s))' % ', '.join(items)
    first = v.get_default_value(check)
    expected = list(first)
    first.append('MUTATED')
    second = v.get_default_value(check)
    assert second == expected
```

**Failing input**: `items=['0']` (i.e. the check string `pass(default=list(0))`)

## Reproducing the Bug

```python
from configobj.validate import Validator

v = Validator()
check = "pass(default=list('a', 'b'))"

first = v.get_default_value(check)
first.append('MUTATED')
second = v.get_default_value(check)

assert second == ['a', 'b'], second   # AssertionError: ['a', 'b', 'MUTATED']
```

End-to-end through `ConfigObj`, two sections share one list object:

```python
from configobj import ConfigObj
from configobj.validate import Validator

spec = ["[__many__]", "items = pass(default=list('a', 'b'))"]
conf = ConfigObj({'s1': {}, 's2': {}}, configspec=spec)
conf.validate(Validator())

assert conf['s1']['items'] is not conf['s2']['items']   # AssertionError
conf['s1']['items'].append('zzz')
assert conf['s2']['items'] == ['a', 'b']                # AssertionError
```

## Why This Is A Bug

`_parse_with_caching` (validate.py:636-647) states its own intent in a comment:

```python
if check in self._cache:
    fun_name, fun_args, fun_kwargs, default = self._cache[check]
    # We call list and dict below to work with *copies* of the data
    # rather than the original (which are mutable of course)
    fun_args = list(fun_args)
    fun_kwargs = dict(fun_kwargs)
```

`default` is the fourth element of that same cached tuple and is just as mutable — a
`default=list(...)` parameter is parsed by `_list_handle` into a Python `list` — but it is
handed out by reference, both from the cache branch and from the freshly-parsed branch
(where the same object is also stored into `self._cache`). `pass(default=list(1, 2, 3, 4))`
is a form the module's own doctests exercise (validate.py:1388, 1397), so this is a
supported spelling, not an exotic one.

Consequences: a single `conf['section']['key'].append(x)` permanently poisons the
`Validator`'s cache, so every later `check()`/`get_default_value()` for that check string
returns the mutated list; and all config entries defaulted from one spec string alias a
single object, so writing to one writes to all. Both failures are silent.

Checks that build a new list on the way out (`is_list`, `force_list`, `is_mixed_list`) hide
the aliasing; pass-through checks (`pass`, `''`, user-registered functions that return the
value unchanged) expose it.

The same shallow-copy gap applies to list-valued *keyword* arguments: `dict(fun_kwargs)`
copies the dict but not the lists inside it, so a check function that mutates a
`key=list(...)` argument corrupts the cache in the same way.

## Fix

Copy the default on the way out of the cache, in both branches:

```diff
--- a/src/configobj/validate.py
+++ b/src/configobj/validate.py
@@ -640,6 +640,8 @@ class Validator(object):
             fun_args = list(fun_args)
             fun_kwargs = dict(fun_kwargs)
         else:
             fun_name, fun_args, fun_kwargs, default = self._parse_check(check)
             fun_kwargs = dict([(str(key), value) for (key, value) in list(fun_kwargs.items())])
             self._cache[check] = fun_name, list(fun_args), dict(fun_kwargs), default
+        if isinstance(default, list):
+            default = list(default)
         return fun_name, fun_args, fun_kwargs, default
```

Verified: with this patch the reproductions above pass and the module's full doctest suite
(198 examples) still passes.

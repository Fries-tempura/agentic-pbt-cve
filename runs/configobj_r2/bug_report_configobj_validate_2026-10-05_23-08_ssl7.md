# Bug Report: configobj.validate Validator.check parses argument strings in quadratic time (ReDoS)

**Target**: `configobj.validate.Validator.check` / `Validator._parse_check`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`Validator._parse_check` pulls arguments out of a check string with `self._paramfinder.findall(arg_string)`. When an unquoted argument contains `=` but no keyword syntax, every start offset scans to the end of the string and then fails. As a result, parse time grows with the square of the argument length. A check string of only 16 KB takes about 7 s to parse, and 160 KB takes about 12 minutes. The `_matchfinder` pre-check does not stop this, because `'^%s*'` always matches. Anyone who can control a configspec (or a string passed to `Validator.check` / `get_default_value`) can use this to tie up the process (CVE-2023-26112 class).

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
from configobj.validate import Validator, ValidateError

@settings(max_examples=60, deadline=None)
@given(st.text(alphabet="(),=\"' ab", min_size=1, max_size=4), st.integers(500, 3000))
def test_parse_is_fast(chunk, n):
    spec = chunk * n
    t = time.perf_counter()
    try:
        Validator().check(spec, "x")
    except (ValidateError, SyntaxError, TypeError):
        pass
    assert time.perf_counter() - t < 1.0, (chunk, n)
```

The random search did not cross the 1 s threshold at these sizes. A targeted timing probe built from the same chunk family (`"f(" + "a"*n + "=)"`) showed the quadratic curve: 0.03 s at n=1000, 0.11 s at 2000, 0.43 s at 4000, 1.8 s at 8000, and 6.9 s at 16000.

**Failing input**: `"integer(" + "a" * 16000 + "=)"`

## Reproducing the Bug

```python
import time
from configobj.validate import Validator

for n in (4000, 8000, 16000):
    t = time.perf_counter()
    try:
        Validator().check("integer(" + "a" * n + "=)", "1")
    except Exception:
        pass
    print(n, round(time.perf_counter() - t, 2))
```

Output (configobj 5.0.8):
```
4000 0.43
8000 1.78
16000 6.92
```

## Why This Is A Bug

A check string is a short `name(args)` expression, and parsing one should take time proportional to its length. Instead, `findall` restarts the `_paramfinder` regex at every character offset, and the lazy unquoted branch `[^'",\s=][^,=]*?` runs forward to the `=` each time before failing. That gives O(n²) work on input that is plainly malformed. The `_matchfinder` check, which is meant to reject bad syntax first, cannot reject anything, so the `raise VdtParamError(...)` beneath it can never run. That raise is broken anyway: it passes one argument to a two-argument constructor, so if it ever ran it would raise `TypeError`.

## Fix

Scan the arguments left to right with anchored `match` calls, so the regex is never restarted at each offset, and reject input that cannot be consumed. The patch below also fixes the broken `VdtParamError` calls. With the patch, the 16 KB input is rejected with `VdtParamError` in about 2 ms. All module doctests pass, and the patched parser gave the same result as the original on 3000 random inputs that it accepts.

```diff
--- a/src/configobj/validate.py
+++ b/src/configobj/validate.py
@@ -664,11 +664,21 @@ class Validator(object):
             arg_match = self._matchfinder.match(arg_string)
             if arg_match is None:
                 # Bad syntax
-                raise VdtParamError('Bad syntax in check "%s".' % check)
+                raise VdtParamError('check', check)
             fun_args = []
             fun_kwargs = {}
-            # pull out args of group 2
-            for arg in self._paramfinder.findall(arg_string):
+            # pull out args of group 2, scanning left to right so the
+            # regex is never restarted at every character offset
+            args = []
+            pos = 0
+            while pos < len(arg_string):
+                param_match = self._paramfinder.match(arg_string, pos)
+                if param_match is None or param_match.end() == pos:
+                    raise VdtParamError('check', check)
+                args.append(param_match.group(1))
+                pos = param_match.end()
+            for arg in args:
                 # args may need whitespace removing (before removing quotes)
                 arg = arg.strip()
                 listmatch = self._list_arg.match(arg)
```

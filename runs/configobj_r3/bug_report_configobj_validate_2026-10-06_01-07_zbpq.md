# Bug Report: configobj.validate Catastrophic Backtracking (ReDoS) in `Validator.check`

**Target**: `configobj.validate.Validator` (`_func_re` used by `check` / `_parse_check`)
**Severity**: Medium
**Bug Type**: Crash (Denial of Service)
**Date**: 2026-10-06

## Summary

`Validator.check` parses the check string with `_func_re = re.compile(r'(.+?)\((.*)\)')`. The
unbounded `.+?` and `.*` over a string rich in parentheses causes quadratic regex backtracking,
so a short, attacker-influenced check string can hang the parser (ReDoS, CWE-1333). This is
CVE-2023-26112, still present in this checkout (fixed in 5.0.9).

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
from configobj.validate import Validator

@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=0, max_value=30000))
def test_check_parsing_is_not_superlinear(i):
    v = Validator()
    attack = '\x00' * i + ')' + '(' * i
    t = time.perf_counter()
    try:
        v.check(attack, 'aaa')
    except Exception:
        pass
    elapsed = time.perf_counter() - t
    assert elapsed < 0.5, 'len=%d took %.2fs (super-linear backtracking)' % (len(attack), elapsed)
```

**Failing input**: `i = 15840` (check string length 31681, ~0.5s); cost grows quadratically.

## Reproducing the Bug

```python
import time
from configobj.validate import Validator

v = Validator()
for i in (2000, 4000, 8000, 16000):
    attack = '\x00' * i + ')' + '(' * i
    t = time.perf_counter()
    try:
        v.check(attack, 'aaa')
    except Exception:
        pass
    print(i, round(time.perf_counter() - t, 3))
```

Output shows a clean 4× time increase for each 2× size increase (0.008 → 0.031 → 0.128 →
0.504s). Extrapolating to the published PoC size (`i = 165100`) yields ~50s of CPU for a
single call.

## Why This Is A Bug

`Validator.check` places no limit on the length of a check string and makes no claim that
certain inputs are forbidden; it either validates or raises a `ValidateError` subclass. A
check string that happens to contain many parentheses (e.g. derived from a server-side
configuration whose values a developer interpolates into a spec) instead consumes CPU time
quadratic in its length before finally raising `VdtUnknownCheckError`. This allows a
denial-of-service with a small input, which is the documented CVE-2023-26112.

## Fix

Anchor the function-name group so it cannot span parentheses, eliminating the ambiguous
backtracking (the upstream 5.0.9 fix):

```diff
--- a/src/configobj/validate.py
+++ b/src/configobj/validate.py
@@ -541,7 +541,7 @@ class Validator(object):
     """

     # this regex does the initial parsing of the checks
-    _func_re = re.compile(r'(.+?)\((.*)\)', re.DOTALL)
+    _func_re = re.compile(r'([^\(\)]+?)\((.*)\)', re.DOTALL)
```

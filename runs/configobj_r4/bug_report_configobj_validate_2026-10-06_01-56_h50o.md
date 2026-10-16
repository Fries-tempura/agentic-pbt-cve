# Bug Report: configobj.validate Quadratic-time (ReDoS) parsing of check strings

**Target**: `configobj.validate.Validator.check` / `Validator._func_re`
**Severity**: Medium
**Bug Type**: Logic (performance / denial of service)
**Date**: 2026-10-06

## Summary

`Validator` parses check strings with `_func_re = re.compile(r'(.+?)\((.*)\)', re.DOTALL)`. If a check string contains `(` but no closing `)`, the regex tries every possible split point for `(.+?)`, and for each one `(.*)` scans to the end and then backtracks. That makes parsing O(n²). A configspec of about 16 KB takes about 0.5 s to parse one check, and the time grows quadratically after that (CVE-2023-26112).

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st, HealthCheck
from configobj.validate import Validator, ValidateError, VdtParamError

@settings(max_examples=50, deadline=None, suppress_health_check=list(HealthCheck))
@given(unit=st.text(alphabet='a(=, ', min_size=1, max_size=3).filter(lambda u: '(' in u),
       n=st.integers(5000, 20000))
def test_check_parse_time_linearish(unit, n):
    check = unit * n
    t = time.perf_counter()
    try:
        Validator().check(check, '1')
    except (ValidateError, VdtParamError):
        pass
    assert time.perf_counter() - t < 0.5, (repr(unit), n, time.perf_counter() - t)
```

**Failing input**: `unit='(', n=14504`

## Reproducing the Bug

```python
import time
from configobj.validate import Validator

for n in [4000, 8000, 16000]:
    t = time.time()
    try:
        Validator().check('a' + '(' * n, '1')
    except Exception:
        pass
    print(n, round(time.time() - t, 3))
```

Output: `4000 0.032`, `8000 0.126`, `16000 0.494`. Each doubling of the input multiplies the time by about 4.

## Why This Is A Bug

Check strings come from configspec files. Those files may come from users or other untrusted sources. Parsing a short malformed string should take linear time. With the current regex, an attacker who controls the configspec can use a lot of CPU time with a small input. This was reported as CVE-2023-26112.

## Fix

```diff
-    _func_re = re.compile(r'(.+?)\((.*)\)', re.DOTALL)
+    _func_re = re.compile(r'([^\(\)]+?)\((.*)\)', re.DOTALL)
```

With this change, `'a' + '(' * 16000` is rejected in about 70 µs.

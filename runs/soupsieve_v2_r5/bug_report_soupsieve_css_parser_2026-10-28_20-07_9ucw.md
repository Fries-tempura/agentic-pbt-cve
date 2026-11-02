# Bug Report: soupsieve.css_parser parse time grows quadratically with selector length (ReDoS)

**Target**: `soupsieve.css_parser` (`IDENTIFIER` / `PAT_TAG`, `RE_WS_END`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

Parsing a selector takes time quadratic in its length in two separate places. The first is any long identifier, e.g. the valid tag selector `'a' * n`. The second is any long run of whitespace that does not end the pattern. A 20,000-character selector takes 7–10 seconds to compile, so `soupsieve.select(user_selector, …)` can be used for denial of service.

## Property-Based Test

```python
UNIT = st.sampled_from(['a', '-', ' ', '\t', '/**/', '\\41 ', '!', '.', '#', ',', ':'])

@settings(max_examples=40, deadline=None, suppress_health_check=list(HealthCheck))
@given(prefix=st.lists(UNIT, max_size=3).map(''.join),
       unit=st.lists(UNIT, min_size=1, max_size=3).map(''.join),
       suffix=st.lists(UNIT, max_size=3).map(''.join))
def test_linear_cost(prefix, unit, suffix):
    """CLAIM-1: parse cost grows linearly with selector length."""
    n = 1000
    small = prefix + unit * n + suffix
    big = prefix + unit * (4 * n) + suffix
    t_small = max(min(cost(small) for _ in range(2)), 1e-3)
    t_big = min(cost(big) for _ in range(2))
    assert t_big / t_small < 10 or t_big < 0.05, (repr(unit), t_small, t_big)
```

**Failing input**: `prefix='', unit='a', suffix=''`. At 4× the length it took 17× the time (0.017 s → 0.28 s).

## Reproducing the Bug

```python
import time
import soupsieve as sv

for n in (2000, 4000, 8000, 20000):
    for s in ('a' * n, 'a' + ' ' * n + 'b'):
        t = time.perf_counter()
        sv.compile(s)
        print(n, round(time.perf_counter() - t, 2))
```

Output on this checkout: 0.07/0.10, 0.29/0.41, 1.17/1.52, 7.2/9.7 seconds. The same script on the released soupsieve 2.9 wheel runs in about 0.001 s for every size.

## Why This Is A Bug

Parsing a selector should cost time proportional to its length. Two regexes in this checkout backtrack quadratically:

1. `IDENTIFIER` is `(?:-?(?:X|esc)+|--)(?:Y|esc)*`, where X ⊂ Y. `PAT_TAG` first tries the optional `tag_ns` group, `IDENTIFIER\|`. On `aaaa…` with no `|`, the regex backtracks through every split between `X+` and `Y*`, which costs O(n²).
2. `RE_WS_END = re.compile(fr'{WSC}*$')` is used with `.search()`. At every start position inside a whitespace run, `WSC*` consumes to the end of the run and then fails on `$`, which costs O(n²).

## Fix

```diff
-COMMENTS = r'(?:/\*[^*]*\*+(?:[^/*][^*]*\*+)*/)'
+COMMENTS = r'(?:/\*(?:[^*]|\*(?!/))*\*/)'
@@
-(?:(?:-?(?:[^\x00-\x2f\x30-\x40\x5B-\x5E\x60\x7B-\x9f]|{CSS_ESCAPES})+|--)
+(?:(?:--|-?(?:[^\x00-\x2f\x30-\x40\x5B-\x5E\x60\x7B-\x9f]|{CSS_ESCAPES}))
@@
-RE_WS_END = re.compile(fr'{WSC}*$')
+RE_WS_END = re.compile(fr'^(?:[ \t]|(?:\n\r|(?!\n\r)[\n\f\r])|{COMMENTS})*')
@@
-        m = RE_WS_END.search(pattern)
-        end = (m.start(0) - 1) if m else (len(pattern) - 1)
+        m = RE_WS_END.search(pattern[::-1])
+        offset = m.end(0) if m else 0
+        end = len(pattern) - (1 + offset)
```

This patch restores the released 2.9 code. The identifier starts with exactly one start unit, so there is no ambiguous split. Trailing whitespace is found by an anchored match on the reversed string. The reversed regex needs `/*` to close comments, and that still works because `COMMENTS` is written so it does not depend on direction.

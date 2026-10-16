# Bug Report: configobj.validate Catastrophic Backtracking (ReDoS) in `Validator.check`

**Target**: `configobj.validate.Validator.check` (parameter-parsing regexes)
**Severity**: High
**Bug Type**: Crash (Denial of Service via catastrophic regex backtracking)
**Date**: 2026-10-06

## Summary

`Validator.check` parses the check/schema string with the `_matchfinder`
regex (built from `_paramstring`). A check string containing an unterminated
`list(` followed by many whitespace-padded, comma-separated members causes
catastrophic (exponential) backtracking. Instead of quickly raising
`VdtParamError: Bad syntax`, parsing time roughly quadruples per added member,
hanging the process on inputs only a few dozen characters long.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
from configobj.validate import Validator

def capture(value, *args, **kwargs):
    return args, kwargs

@given(st.text(alphabet="a ,='\"()", max_size=40))
@settings(max_examples=500, deadline=None)
def test_check_parse_fast(argstr):
    v = Validator({'cap': capture})
    t = time.perf_counter()
    try:
        v.check('cap(%s)' % argstr, 'x')
    except Exception:
        pass
    assert time.perf_counter() - t < 0.5
```

**Failing input**: any check string of the form
`"string_list(default=list(" + "a , " * n + ")"` (unterminated inner `list(`),
e.g. `n = 14`. Minimal failing shape: an unclosed `list(` with repeated
`"<token> , "` members.

## Reproducing the Bug

```python
import time
from configobj.validate import Validator

v = Validator()
for n in [10, 12, 14]:
    s = "string_list(default=list(" + "a , " * n + ")"
    t = time.perf_counter()
    try:
        v.check(s, "x")
    except Exception:
        pass
    print(n, round(time.perf_counter() - t, 3), "s")
```

Observed timings:

```
10  0.288 s
12  4.798 s
14  ~75 s   (does not finish in reasonable time)
```

Each additional member multiplies runtime by ~4, i.e. exponential.

## Why This Is A Bug

The check string is malformed (the inner `list(` is never closed — a realistic
typo in a hand-written ConfigObj configspec). `_parse_check` is designed to
reject such input *quickly* with `VdtParamError('Bad syntax in check ...')`.
Instead, `_matchfinder.match(arg_string)` enters catastrophic backtracking
because the `list(...)` alternative in `_paramstring` nests quantifiers over
optional whitespace and repeated members:

```
...=list(
    (?: \s* (?: "..." | '...' | [^'",\s\)][^,\)]*? ) \s*,\s* )*
    ...
)
```

When the closing `)` is absent, the outer `*` and the inner alternatives can
partition the ` , ` runs in exponentially many ways before failing. A ~40
character string can freeze the interpreter. Where configspecs are influenced
by untrusted input this is a denial-of-service vector. This is the class of
issue tracked as CVE-2023-26112 for configobj.

## Fix

Make the whitespace handling in the list sub-pattern unambiguous (no two
regex pieces able to consume the same spaces), e.g. require members to be
separated by exactly one comma with surrounding whitespace folded into a single
non-backtracking construct, or use an atomic group / possessive quantifier for
the member repetition. A minimal, behaviour-preserving change is to anchor the
list-member separator so the `*`-repeated group cannot overlap with the final
optional member. A robust alternative is to replace the hand-rolled regex
parser with a non-backtracking tokenizer for the argument list.

```diff
--- a/src/configobj/validate.py
+++ b/src/configobj/validate.py
@@
-_paramstring = r'''
+# Disallow the inner member body from matching whitespace that the
+# separator also matches, preventing ambiguous partitions of " , " runs
+# that drive catastrophic backtracking when the closing ")" is missing.
+_paramstring = r'''
     (?:
         (
             (?:
                 [a-zA-Z_][a-zA-Z0-9_]*\s*=\s*list\(
                     (?:
-                        \s*
+                        \s*+
                         (?:
                             (?:".*?")|              # double quotes
                             (?:'.*?')|              # single quotes
                             (?:[^'",\s\)][^,\)]*?)       # unquoted
                         )
-                        \s*,\s*
+                        \s*+,\s*+
                     )*
```

(Possessive quantifiers `*+` require the `regex` module or Python 3.11+;
for broad compatibility, prefer rewriting the list parsing as an explicit
tokenizer that splits on commas outside quotes.)

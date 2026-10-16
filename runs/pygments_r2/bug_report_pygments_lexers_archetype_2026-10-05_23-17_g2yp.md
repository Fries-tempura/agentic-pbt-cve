# Bug Report: pygments.lexers.archetype Quadratic-time lexing of whitespace runs (ReDoS)

**Target**: `pygments.lexers.archetype.AdlLexer`, `pygments.lexers.archetype.CadlLexer`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`AdlLexer` (root state) and `CadlLexer` (`any_code` state, entered after `[`) take time quadratic in the length of a run of spaces/tabs that is not followed by a newline. Each candidate rule (`archetype_id`'s `([ \t]*)` prefix, `([ \t]*)(\()`, `\s*\n`, `(\s*)(,)(\s*)`) scans the whole run before failing. No rule consumes plain blanks in these states, so the lexer emits a one-character `Error` token and repeats the scan from the next position. 16 KB of input takes about 5 s, and 64 KB takes about 85 s. Pygments is commonly run on untrusted input, such as code highlighting in web apps, so this is a denial-of-service vector.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
from pygments.lexers.archetype import AdlLexer, CadlLexer

def _time(lx, s):
    t = time.perf_counter()
    list(lx().get_tokens(s))
    return time.perf_counter() - t

@settings(max_examples=30, deadline=None)
@given(st.sampled_from([(AdlLexer, ""), (CadlLexer, "[")]),
       st.sampled_from([" ", "\t"]),
       st.sampled_from(["x", "!", "#"]))
def test_whitespace_run_scales_linearly(lx_prefix, ws, tail):
    lx, prefix = lx_prefix
    small = _time(lx, prefix + ws * 2000 + tail)
    big = _time(lx, prefix + ws * 16000 + tail)
    assert big < max(small, 1e-3) * 8 * 3
```

**Failing input**: `lx_prefix=(AdlLexer, ''), ws=' ', tail='x'` (8x input → ~62x time: 0.086 s → 5.34 s)

## Reproducing the Bug

```python
import time
from pygments.lexers.archetype import AdlLexer, CadlLexer

for n in (4000, 8000, 16000):
    for lx, s in ((AdlLexer, " " * n + "x"), (CadlLexer, "[" + " " * n + "x")):
        t = time.perf_counter()
        list(lx().get_tokens(s))
        print(lx.__name__, n, round(time.perf_counter() - t, 2))
```

Output: 0.34 s / 1.3 s / 5.3 s. The time roughly quadruples each time the input doubles.

## Why This Is A Bug

A lexer for a highlighting library should tokenize in roughly linear time. Here a short, valid-looking input (indentation followed by text) can stall the process for seconds to minutes. This is the classic ReDoS pattern, where many overlapping failed regex scans add up, and attackers can trigger it with any input that reaches these lexers. These are selectable by alias (`adl`, `cadl`) and by filename (`*.adl`, `*.adls`, `*.cadl`).

A related, smaller inefficiency is that `archetype_id` contains `\.\w+[\w-]*`. This is ambiguous and equivalent to `\.\w[\w-]*`. It makes inputs like `aa-aa-aa.` + `a`*n quadratic as well (16 KB → 6.8 s).

## Fix

Add a rule that consumes blank runs in one step. I checked this on the shipped `tests/examplefiles/{adl,cadl}` inputs, and the token streams are identical. Lexing time becomes linear: 64 KB takes about 3 ms.

```diff
--- a/pygments/lexers/archetype.py
+++ b/pygments/lexers/archetype.py
@@ class AtomsLexer(RegexLexer):
         'archetype_id': [
             (r'([ \t]*)(([a-zA-Z]\w+(\.[a-zA-Z]\w+)*::)?[a-zA-Z]\w+(-[a-zA-Z]\w+){2}'
-             r'\.\w+[\w-]*\.v\d+(\.\d+){,2}((-[a-z]+)(\.\d+)?)?)',
+             r'\.\w[\w-]*\.v\d+(\.\d+){,2}((-[a-z]+)(\.\d+)?)?)',
              bygroups(Whitespace, Name.Decorator)),
         ],
@@
             # handle use_archetype statement
             (r'(\s*)(,)(\s*)', bygroups(Whitespace, Punctuation, Whitespace)),
+            (r'\s+', Whitespace),
         ],
@@ class AdlLexer(AtomsLexer):
             include('archetype_id'),
             (r'([ \t]*)(\()', bygroups(Whitespace, Punctuation), 'metadata'),
             include('whitespace'),
+            (r'[ \t]+', Whitespace),
         ],
```

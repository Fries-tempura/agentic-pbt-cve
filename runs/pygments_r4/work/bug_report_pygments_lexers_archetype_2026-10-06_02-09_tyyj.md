# Bug Report: pygments.lexers.archetype AdlLexer takes quadratic time on long unmatched runs

**Target**: `pygments.lexers.archetype.AdlLexer`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`AdlLexer`'s `root` state has no fallback rule for ordinary text. When it hits text that no rule matches, it emits one `Error` token per character. At every character, the `archetype_id`, `([ \t]*)(\()` and `\s*\n` rules each scan to the end of the run before failing. As a result, lexing time grows quadratically with input length: 16 KB of spaces takes about 10 seconds. This lets untrusted input cause a denial of service, for example in a web app that highlights user-supplied `.adl` files.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
from pygments.lexers.archetype import AdlLexer

def lex_time(s):
    t = time.perf_counter(); list(AdlLexer().get_tokens(s)); return time.perf_counter() - t

@settings(max_examples=10, deadline=None)
@given(st.sampled_from([" ", "\t", "a", "aa.", "x1"]))
def test_adl_lexing_scales_linearly(unit):
    small = lex_time(unit * 2000 + "!")
    big = lex_time(unit * 16000 + "!")
    assert big < 20 * max(small, 0.005), (unit, small, big)
```

**Failing input**: `unit=' '` (2000 spaces: 0.15 s; 16000 spaces: 9.6 s, so 8x the input takes about 63x the time)

## Reproducing the Bug

```python
import time
from pygments.lexers.archetype import AdlLexer

for n in (4000, 8000, 16000):
    t = time.perf_counter()
    list(AdlLexer().get_tokens(" " * n + "x"))
    print(n, round(time.perf_counter() - t, 2))
```

## Why This Is A Bug

Lexers are expected to run in roughly linear time; Pygments treats super-linear regex behaviour on crafted input as a ReDoS/DoS issue. `OdinLexer` and `CadlLexer` handle the same input in milliseconds. `AdlLexer` (registered for `*.adl`, `*.adls`, `*.adlf`, `*.adlx`) is slow because its `root` state only matches whitespace runs that end in a newline. It has no rule that consumes horizontal whitespace or words on their own, so every character falls through to error recovery, and each attempt rescans the rest of the run. Inputs such as `"a" * n` and `"aa." * n` show the same quadratic growth.

## Fix

Add rules to `AdlLexer`'s `root` that consume runs of characters the other rules don't match. The patch below fixes the space/tab and word cases (16000 chars now lex in a few ms). Dotted runs like `"aa." * n` are still quadratic because of the `(...(\.[a-zA-Z]\w+)*::)?` prefix of `archetype_id`, which needs anchoring or a possessive/atomic group.

```diff
--- a/pygments/lexers/archetype.py
+++ b/pygments/lexers/archetype.py
@@ class AdlLexer(AtomsLexer):
             include('archetype_id'),
             (r'([ \t]*)(\()', bygroups(Whitespace, Punctuation), 'metadata'),
             include('whitespace'),
+            (r'[ \t]+', Whitespace),
+            (r'\w+', Text),
         ],
     }
```

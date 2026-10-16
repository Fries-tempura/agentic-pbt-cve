# Bug Report: pygments.lexers.archetype AdlLexer takes quadratic time on long words or whitespace runs

**Target**: `pygments.lexers.archetype.AdlLexer`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`AdlLexer`'s `root` state has no rule that consumes ordinary words or runs of spaces and tabs that aren't followed by a newline. The lexer therefore emits one `Error` token per character. Before each of those, the `archetype_id`, `([ \t]*)(\()` and `\s*\n` regexes each rescan the rest of the run, so tokenizing costs O(n²). A 20 KB line of letters or spaces takes about 10 seconds, so a small untrusted input can tie up a CPU (a ReDoS-style DoS). This matters for any service that highlights `.adl` files or uses `guess_lexer`.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
from pygments.lexers.archetype import AdlLexer

@settings(max_examples=20, deadline=None)
@given(st.sampled_from(["a", "Z", "_", " ", "\t"]))
def test_adl_scales_linearly(ch):
    def t(n):
        s = time.perf_counter(); list(AdlLexer().get_tokens(ch * n + "x")); return time.perf_counter() - s
    small, big = t(2000), t(8000)
    assert big < 8 * max(small, 1e-3), (small, big)
```

**Failing input**: `ch='a'` (0.13 s for 2,000 chars, 1.76 s for 8,000 chars: 4× the input took about 13× the time)

## Reproducing the Bug

```python
import time
from pygments.lexers.archetype import AdlLexer

for n in [5000, 10000, 20000]:
    t = time.perf_counter()
    list(AdlLexer().get_tokens("a" * n))
    print(n, round(time.perf_counter() - t, 2))
```

Output: `5000 0.7`, `10000 2.71`, `20000 11.3`. `" " * n + "x"` scales the same way (0.59 s, 2.36 s, 9.58 s).

## Why This Is A Bug

Lexer run time should grow linearly with input size. Here, twice the input takes about four times as long, and every character becomes an `Error` token. `OdinLexer` and `CadlLexer` handle the same inputs in about 1 ms because their `whitespace` / `\w`-based rules consume the run in one step.

## Fix

```diff
--- a/pygments/lexers/archetype.py
+++ b/pygments/lexers/archetype.py
@@ class AdlLexer(AtomsLexer):
         'root': [
             (r'^(archetype|template_overlay|operational_template|template|'
              r'speciali[sz]e)', Generic.Heading),
@@
             include('archetype_id'),
             (r'([ \t]*)(\()', bygroups(Whitespace, Punctuation), 'metadata'),
             include('whitespace'),
+            (r'[ \t]+', Whitespace),
+            (r'\w+', Text),
         ],
```

With this patch, the 20,000-char inputs tokenize in about 2 ms. (Separately, the `\.\w+[\w-]*\.v` part of `archetype_id` has overlapping quantifiers. Tightening it to `\.\w[\w-]*\.v` would remove that extra backtracking.)

# Bug Report: pygments.lexers.archetype AdlLexer takes quadratic time (ReDoS) on long runs of letters or spaces

**Target**: `pygments.lexers.archetype.AdlLexer`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`AdlLexer`'s run time grows quadratically with the input on lines made of long runs of letters, or long runs of spaces and tabs with no newline. About 20 KB of `a` characters, or about 20 KB of spaces, takes roughly 10 s in `pygments.highlight`. Attacker-controlled `.adl` content can therefore stall any service that highlights it, such as a wiki, a code host or a documentation build. This is a regular-expression denial-of-service (ReDoS).

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
from pygments.lexers.archetype import AdlLexer

@settings(max_examples=20, deadline=None)
@given(st.integers(4000, 16000), st.sampled_from(['a', ' ', 'aa-aa-aa.a']))
def test_adl_lexing_is_fast(n, ch):
    s = ch * n
    t = time.perf_counter()
    list(AdlLexer().get_tokens(s))
    assert time.perf_counter() - t < 0.5
```

**Failing input**: `n=4000, ch='a'` (0.4 s; each doubling of `n` makes it about 4× slower: 8000 → 1.7 s, 16000 → 7.4 s)

## Reproducing the Bug

```python
import time
from pygments import highlight
from pygments.formatters import NullFormatter
from pygments.lexers import AdlLexer

for payload in ('a' * 20000, ' ' * 20000 + 'x', 'aa-aa-aa.' + 'a' * 20000):
    t = time.perf_counter()
    highlight(payload, AdlLexer(), NullFormatter())
    print(len(payload), round(time.perf_counter() - t, 2), 's')
```

Output (Pygments 2.19.2, CPython 3.14): about 10.2 s, 8.5 s and 11.0 s.

## Why This Is A Bug

The ADL `root` state has no rule that consumes a plain word or a run of spaces. For each character in such a run:

1. Every rule is retried, and each one scans forward to the end of the run. The `archetype_id` rule does this with `[a-zA-Z]\w+` and `[ \t]*`, the `metadata` opener with `[ \t]*`, and the `whitespace` rule with `\s*\n`.
2. All of them fail.
3. `RegexLexer` emits a single-character `Error` token and moves forward one character.

That is O(n) work at each of n positions, so O(n²) in total. Separately, `\.\w+[\w-]*` inside `archetype_id` is ambiguous: `\w+` and `[\w-]*` overlap. After a valid ID prefix such as `aa-aa-aa.`, this makes even a single match attempt O(n²).

A syntax highlighter is expected to run in roughly linear time on any input. Pygments is routinely run on untrusted content, and quadratic blow-up here lets small inputs cause denial of service.

## Fix

```diff
--- a/pygments/lexers/archetype.py
+++ b/pygments/lexers/archetype.py
@@ -37,7 +37,7 @@ class AtomsLexer(RegexLexer):
         'archetype_id': [
             (r'([ \t]*)(([a-zA-Z]\w+(\.[a-zA-Z]\w+)*::)?[a-zA-Z]\w+(-[a-zA-Z]\w+){2}'
-             r'\.\w+[\w-]*\.v\d+(\.\d+){,2}((-[a-z]+)(\.\d+)?)?)',
+             r'\.\w[\w-]*\.v\d+(\.\d+){,2}((-[a-z]+)(\.\d+)?)?)',
              bygroups(Whitespace, Name.Decorator)),
         ],
@@ -311,5 +311,9 @@ class AdlLexer(AtomsLexer):
             include('archetype_id'),
             (r'([ \t]*)(\()', bygroups(Whitespace, Punctuation), 'metadata'),
             include('whitespace'),
+            # consume whole runs so the rules above are not retried at every
+            # character (avoids quadratic run time)
+            (r'[a-zA-Z]\w*', Error),
+            (r'[ \t]+', Whitespace),
         ],
     }
```

(`Error` must be added to the `pygments.token` import.)

I checked this patch with Hypothesis against the original lexer, using 2,000 generated ADL-like inputs that mix headings, archetype IDs, metadata and punctuation. After merging adjacent tokens of the same type, the output was identical. The only intended difference is that runs of spaces and tabs not followed by a newline are now `Whitespace` instead of per-character `Error`. On 20 KB payloads the run time drops from about 10 s to about 2 ms.

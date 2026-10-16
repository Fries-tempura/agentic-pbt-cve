# Bug Report: pygments.lexers.archetype AdlLexer takes quadratic time on long words / whitespace runs (ReDoS)

**Target**: `pygments.lexers.archetype.AdlLexer` (`AtomsLexer.tokens['archetype_id']`)
**Severity**: Medium
**Bug Type**: Logic (performance / ReDoS)
**Date**: 2026-10-06

## Summary

`AdlLexer` tokenizes a single long run of word characters (or a long run of spaces/tabs not followed by a newline) in quadratic time. A 20 KB input such as `"a" * 20000` takes ~10 s; 100 KB takes several minutes. Any service that highlights untrusted input with the ADL lexer (or via `guess_lexer`/filename `*.adl`) can be stalled.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
from pygments.lexers.archetype import AdlLexer

@settings(max_examples=20, deadline=None)
@given(st.characters(whitelist_categories=['Ll', 'Lu']),
       st.characters(whitelist_categories=['Ll', 'Lu', 'Nd']))
def test_linear_time(c1, c2):
    def run(n):
        s = c1 + c2 * n
        t0 = time.perf_counter(); list(AdlLexer().get_tokens(s)); return time.perf_counter() - t0
    small, big = run(2000), run(20000)
    assert big < 30 * small + 0.05, (small, big)
```

**Failing input**: `c1='a', c2='a'` (i.e. `"a" * 20001`) — 10x input size gives ~100x runtime.

## Reproducing the Bug

```python
import time
from pygments.lexers.archetype import AdlLexer

for n in [5000, 10000, 20000]:
    t0 = time.time()
    list(AdlLexer().get_tokens("a" * n))
    print(n, round(time.time() - t0, 2))

t0 = time.time()
list(AdlLexer().get_tokens(" " * 20000 + "x"))
print("spaces", round(time.time() - t0, 2))
```

Observed:
```
5000 0.60
10000 2.40
20000 9.82
```

## Why This Is A Bug

`AdlLexer.root` has no rule that consumes a run of ordinary word characters or bare spaces/tabs. At every position the `archetype_id` regex
`([ \t]*)(([a-zA-Z]\w+(\.[a-zA-Z]\w+)*::)?[a-zA-Z]\w+(-[a-zA-Z]\w+){2}...)` is tried first; its `\w+` (or the leading `[ \t]*`) scans to the end of the run before failing, after which `RegexLexer` emits a single-character `Error` token and advances by one. That is O(n) work at each of n positions → O(n²). Pygments treats such super-linear lexer behaviour on crafted input as a ReDoS vulnerability (lexers are routinely run on untrusted input, e.g. by forges, wikis and pastebins).

## Fix

Prevent `archetype_id` from starting in the middle of a word, and let ADL's root consume whitespace runs in one step. Token output for all ADL/cADL/ODIN example files in `tests/examplefiles` is unchanged with this patch, and the inputs above lex in ~15 ms / ~1 ms.

```diff
--- a/pygments/lexers/archetype.py
+++ b/pygments/lexers/archetype.py
@@ -35,7 +35,7 @@
             (r'([ \t]*)(--.*)$', bygroups(Whitespace, Comment)),
         ],
         'archetype_id': [
-            (r'([ \t]*)(([a-zA-Z]\w+(\.[a-zA-Z]\w+)*::)?[a-zA-Z]\w+(-[a-zA-Z]\w+){2}'
+            (r'([ \t]*)(?<!\w)(([a-zA-Z]\w+(\.[a-zA-Z]\w+)*::)?[a-zA-Z]\w+(-[a-zA-Z]\w+){2}'
              r'\.\w+[\w-]*\.v\d+(\.\d+){,2}((-[a-z]+)(\.\d+)?)?)',
              bygroups(Whitespace, Name.Decorator)),
         ],
@@ -311,5 +311,6 @@
             include('archetype_id'),
             (r'([ \t]*)(\()', bygroups(Whitespace, Punctuation), 'metadata'),
             include('whitespace'),
+            (r'[ \t]+', Whitespace),
         ],
     }
```

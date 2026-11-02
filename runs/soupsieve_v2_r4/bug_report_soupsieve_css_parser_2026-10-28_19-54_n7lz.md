# Bug Report: soupsieve.css_parser exponential-time regex backtracking (ReDoS) on CSS escapes in identifiers

**Target**: `soupsieve.css_parser` (`IDENTIFIER` / `CSS_ESCAPES` patterns, reached via `soupsieve.compile`/`select`/`match`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

Compile time for a malformed selector made of repeated CSS hex escapes such as `[\a\a\a…` grows exponentially with its length. It roughly doubles with each extra `\a`, so a 40-character selector takes seconds and about 60 characters is effectively a hang. `[` + `a`*N is also quadratic (3000 characters take about 1.3 s). Any application that passes untrusted selectors to soupsieve (or `BeautifulSoup.select`) can be denied service.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
import soupsieve as sv
from soupsieve import css_parser as cp
from soupsieve.util import SelectorSyntaxError

prefix = st.sampled_from(['[', '', '.', '#', ':is(', ':nth-child(', ':lang(', '[a=', '[a|'])
unit = st.sampled_from(['\\a', '\\1', '\\f', 'a', '\\a ', '-'])

@settings(max_examples=60, deadline=None)
@given(p=prefix, u=unit, n=st.integers(0, 25), tail=st.sampled_from(['', '!', ')', '|']))
def test_compile_cost_repeated(p, u, n, tail):
    """CLAIM-1: compile returns or raises quickly; repeated identifier units."""
    s = p + u * n + tail
    cp._purge_cache()
    t = time.perf_counter()
    try:
        sv.compile(s)
    except (SelectorSyntaxError, NotImplementedError, ValueError):
        pass
    assert time.perf_counter() - t < 1.0, repr(s)
```

**Failing input**: `p='[', u='\\a', n=17, tail=''`, i.e. the selector `'[' + '\\a' * 17`

## Reproducing the Bug

```python
import time
import soupsieve as sv

for n in (12, 14, 16, 18, 20):
    s = '[' + '\\a' * n
    t = time.perf_counter()
    try:
        sv.compile(s)
    except sv.SelectorSyntaxError:
        pass
    print(n, round(time.perf_counter() - t, 3))
```

Observed: 12 → 0.04 s, 14 → 0.17 s, 16 → 0.79 s, 18 → 3.7 s, and each further `\a` roughly doubles it. `:lang(` + `'\\a'*16` takes 2.6 s. `[a=`, `[x|`, `:nth-child(1 of ` and descendant-selector contexts are also affected.

## Why This Is A Bug

Tokenizing a selector should take time roughly linear in its length. Here, inside `IDENTIFIER`, each escape like `\a` can be matched two ways: as a hex escape (`[a-f0-9]{1,6}`), or as a literal-character escape (`[^\r\n\f]`). A run like `\aa` can also be split as hex `a` + ident char `a` or as hex `aa`. On top of that, the identifier's leading `(…)+` and trailing `(…)*` match overlapping character sets. When the enclosing token fails (for example a missing `]`), Python's backtracking regex engine tries every split: 2^n of them. Input length alone cannot be capped low enough to avoid this; 40 bytes is enough.

## Fix

This keeps Python 3.10 compatibility (atomic groups need 3.11+). Each escape now has exactly one parse: the hex form takes the longest run (at most 6 digits), and the literal form excludes hex digits. The identifier head is a single start character, so it can no longer overlap the tail. I checked that it gives the same result (parsed structure or exception type) as the original on 20,000 random selectors built from escape/identifier fragments. All the slow inputs above finish in under 3 ms.

```diff
--- a/soupsieve/css_parser.py
+++ b/soupsieve/css_parser.py
@@ -116,11 +116,11 @@ COMMENTS = r'(?:/\*[^*]*\*+(?:[^/*][^*]*\*+)*/)'
 # Whitespace with comments included
 WSC = fr'(?:{WS}|{COMMENTS})'
 # CSS escapes
-CSS_ESCAPES = fr'(?:\\(?:[a-f0-9]{{1,6}}{WS}?|[^\r\n\f]|$))'
+CSS_ESCAPES = fr'(?:\\(?:(?:[a-f0-9]{{6}}|[a-f0-9]{{1,5}}(?![a-f0-9])){WS}?|[^\r\n\fa-f0-9]|$))'
 CSS_STRING_ESCAPES = fr'(?:\\(?:[a-f0-9]{{1,6}}{WS}?|[^\r\n\f]|$|{NEWLINE}))'
 # CSS Identifier
 IDENTIFIER = fr'''
-(?:(?:-?(?:[^\x00-\x2f\x30-\x40\x5B-\x5E\x60\x7B-\x9f]|{CSS_ESCAPES})+|--)
+(?:(?:-?(?:[^\x00-\x2f\x30-\x40\x5B-\x5E\x60\x7B-\x9f]|{CSS_ESCAPES})|--)
 (?:[^\x00-\x2c\x2e\x2f\x3A-\x40\x5B-\x5E\x60\x7B-\x9f]|{CSS_ESCAPES})*)
 '''
```

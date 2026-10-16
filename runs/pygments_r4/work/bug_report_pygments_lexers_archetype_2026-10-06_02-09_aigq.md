# Bug Report: pygments.lexers.archetype CadlLexer mis-escaped `\u223C` operator

**Target**: `pygments.lexers.archetype.CadlLexer`
**Severity**: Low
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

In `CadlLexer`, the operator rule for the logic symbols (∃ ∄ ∀ ∧ ∨ ⊻ ∼) writes the last one as `\223C` instead of `\u223C`. Python reads that as the octal escape `\223` (U+0093, a C1 control character) followed by the letter `C`. As a result, `∼` (U+223C) is lexed as `Error`, and the meaningless string `"\x93C"` is lexed as `Operator`.

## Property-Based Test

```python
from hypothesis import given, strategies as st
from pygments.lexers.archetype import CadlLexer
from pygments.token import Operator

@given(st.sampled_from(["\u2203", "\u2204", "\u2200", "\u2227", "\u2228", "\u22BB", "\u223C"]))
def test_logic_operator_chars_are_operators(ch):
    toks = list(CadlLexer().get_tokens(f"a {ch} b"))
    assert (Operator, ch) in toks, toks
```

**Failing input**: `ch='∼'`

## Reproducing the Bug

```python
from pygments.lexers.archetype import CadlLexer

print(list(CadlLexer().get_tokens("a \u223C b")))
print(list(CadlLexer().get_tokens("a \x93C b")))
```

Output:
```
[..., (Token.Error, '∼'), ...]
[..., (Token.Operator, '\x93C'), ...]
```

## Why This Is A Bug

Every other entry in this alternation is a `\uXXXX` escape for a logic symbol: `∃` (U+2203), `∄` (U+2204), `∀` (U+2200), `∧` (U+2227), `∨` (U+2228) and `⊻` (U+22BB). The last entry is clearly meant to be U+223C (`∼`, the negation operator), but the `u` is missing. So valid cADL that uses `∼` is highlighted as an error, and a nonsense byte sequence is highlighted as an operator.

## Fix

```diff
--- a/pygments/lexers/archetype.py
+++ b/pygments/lexers/archetype.py
@@ class CadlLexer(AtomsLexer):
             # there_exists / not there_exists / for_all / and / or
-            ('(\u2203|\u2204|\u2200|\u2227|\u2228|\u22BB|\223C)',
+            ('(\u2203|\u2204|\u2200|\u2227|\u2228|\u22BB|\u223C)',
              Operator),
```

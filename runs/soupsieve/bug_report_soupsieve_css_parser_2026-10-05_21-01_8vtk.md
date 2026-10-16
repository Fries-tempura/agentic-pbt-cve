# Bug Report: soupsieve.css_parser escape() output for U+0080–U+009F is rejected by the parser

**Target**: `soupsieve.css_parser.escape` / `IDENTIFIER` pattern
**Severity**: Low
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`escape()` leaves every code point ≥ U+0080 unescaped, which matches CSSOM "serialize an identifier". But the parser's `IDENTIFIER` regex excludes `\x80-\x9f` from identifier characters. So `escape(x)` for any identifier containing a C1 control character yields a selector that the parser rejects with `SelectorSyntaxError`.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from soupsieve import css_parser as cp

idents = st.text(st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"), min_size=1)


@given(idents)
@settings(max_examples=1000)
def test_escaped_id_selector_parses_to_same_id(s):
    sel = cp.CSSParser('#' + cp.escape(s)).process_selectors()
    assert sel.selectors[0].ids == (s,)
```

**Failing input**: `s='\x80'`

## Reproducing the Bug

```python
import soupsieve as sv
from bs4 import BeautifulSoup

soup = BeautifulSoup('<div></div>', 'html.parser')
soup.div['id'] = '\x80'
sv.select('#' + sv.escape('\x80'), soup)
```

```
soupsieve.util.SelectorSyntaxError: Malformed id selector at position 0
```

## Why This Is A Bug

`soupsieve.escape` exists so that arbitrary strings can be safely embedded as identifiers in selectors. Its output should always parse back to the original identifier. Per CSS Syntax Level 3, every "non-ASCII code point" (≥ U+0080) is an ident code point, so `escape` is right and the parser's character classes (`\x7B-\x9f` excluded in `IDENTIFIER`) are too strict. All other characters round-trip correctly (2000+ Hypothesis examples passed once U+0080–U+009F were excluded).

## Fix

```diff
--- a/soupsieve/css_parser.py
+++ b/soupsieve/css_parser.py
@@
 IDENTIFIER = fr'''
-(?:(?:-?(?:[^\x00-\x2f\x30-\x40\x5B-\x5E\x60\x7B-\x9f]|{CSS_ESCAPES})+|--)
-(?:[^\x00-\x2c\x2e\x2f\x3A-\x40\x5B-\x5E\x60\x7B-\x9f]|{CSS_ESCAPES})*)
+(?:(?:-?(?:[^\x00-\x2f\x30-\x40\x5B-\x5E\x60\x7B-\x7f]|{CSS_ESCAPES})+|--)
+(?:[^\x00-\x2c\x2e\x2f\x3A-\x40\x5B-\x5E\x60\x7B-\x7f]|{CSS_ESCAPES})*)
 '''
```

(Alternatively, make `escape()` emit `\80 `-style hex escapes for U+0080–U+009F.)

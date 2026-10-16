# Bug Report: soupsieve.css_parser `escape()` output for U+0080–U+009F cannot be parsed

**Target**: `soupsieve.css_parser.escape` / `IDENTIFIER` pattern
**Severity**: Low
**Bug Type**: Contract
**Date**: 2026-10-06

## Summary

`sv.escape()` leaves every code point >= U+0080 unescaped, as the CSSOM spec says. The parser's `IDENTIFIER` regex, however, excludes `\x7B-\x9f`, so it rejects the C1 range U+0080–U+009F as identifier characters. As a result, `'#' + sv.escape(s)` fails with `SelectorSyntaxError` for any `s` that contains such a character.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
import soupsieve as sv
from bs4 import BeautifulSoup

text = st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"), min_size=1)

@settings(max_examples=500)
@given(text)
def test_escape_produces_valid_id_selector(s):
    soup = BeautifulSoup('<div></div>', 'html.parser')
    soup.div['id'] = s
    assert sv.select_one('#' + sv.escape(s), soup) is soup.div
```

**Failing input**: `s='\x80'`

## Reproducing the Bug

```python
import soupsieve as sv

sv.compile('#' + sv.escape('\x80'))
```

Output: `SelectorSyntaxError: Malformed id selector at position 0`

## Why This Is A Bug

`escape` exists so that any string can be safely embedded as an identifier. In the CSS Syntax spec, an ident code point includes every "non-ASCII code point" (>= U+0080), so the escaped output is valid CSS that soupsieve's own parser rejects. Both halves of the same module disagree: one side should change.

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

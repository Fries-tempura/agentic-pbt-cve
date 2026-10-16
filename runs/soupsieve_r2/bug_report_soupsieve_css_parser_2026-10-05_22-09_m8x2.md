# Bug Report: soupsieve.css_parser `escape()` output for U+0080–U+009F is rejected by the parser

**Target**: `soupsieve.css_parser.escape` / `IDENTIFIER` pattern
**Severity**: Low
**Bug Type**: Contract
**Date**: 2026-10-05

## Summary

`sv.escape()` leaves code points >= 0x80 unescaped, which follows CSSOM "serialize an identifier". But the parser's `IDENTIFIER` regex excludes `\x7B-\x9f`, so it rejects C1 control characters (U+0080–U+009F). As a result, `'#' + sv.escape(x)` raises `SelectorSyntaxError` for any id containing such a character.

## Property-Based Test

```python
@settings(max_examples=1000)
@given(st.text(st.characters(blacklist_categories=('Cs',)), min_size=1))
def test_escape_produces_valid_id_selector(s):
    s = s.replace('\x00', '�')
    sel = cp.CSSParser('#' + cp.escape(s)).process_selectors()
    assert sel[0].ids == (s,)
```

**Failing input**: `s='\x80'`

## Reproducing the Bug

```python
import soupsieve as sv
from bs4 import BeautifulSoup

soup = BeautifulSoup('<p id="\x80">x</p>', 'html.parser')
print(sv.select('#\\80 ', soup))                # works
sv.select('#' + sv.escape('\x80'), soup)       # SelectorSyntaxError: Malformed id selector
```

## Why This Is A Bug

`escape` exists so that any string can be used safely as an identifier in a selector. Its output should always be accepted by the library's own parser. CSS Syntax Level 3 treats every code point >= U+0080 as an ident code point, so the parser regex is what's wrong here.

## Fix

```diff
 IDENTIFIER = fr'''
-(?:(?:-?(?:[^\x00-\x2f\x30-\x40\x5B-\x5E\x60\x7B-\x9f]|{CSS_ESCAPES})+|--)
-(?:[^\x00-\x2c\x2e\x2f\x3A-\x40\x5B-\x5E\x60\x7B-\x9f]|{CSS_ESCAPES})*)
+(?:(?:-?(?:[^\x00-\x2f\x30-\x40\x5B-\x5E\x60\x7B-\x7f]|{CSS_ESCAPES})+|--)
+(?:[^\x00-\x2c\x2e\x2f\x3A-\x40\x5B-\x5E\x60\x7B-\x7f]|{CSS_ESCAPES})*)
 '''
```
(Alternatively, have `escape` hex-escape U+0080–U+009F.)

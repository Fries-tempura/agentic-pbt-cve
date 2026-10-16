# Bug Report: soupsieve.css_parser escape() output for U+0080–U+009F is rejected by the parser

**Target**: `soupsieve.css_parser.escape` / `IDENTIFIER` pattern (`soupsieve.escape`)
**Severity**: Low
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`escape()` leaves every code point >= U+0080 unescaped, which matches CSSOM's "serialize an identifier". The parser's `IDENTIFIER` regex, however, excludes `\x7B-\x9f`, so it rejects the C1 control range U+0080–U+009F. As a result, `sv.compile('.' + sv.escape(s))` raises `SelectorSyntaxError` for any identifier containing those characters.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from soupsieve import css_parser as cp

text = st.text(st.characters(blacklist_characters='\x00', blacklist_categories=('Cs',)))

@settings(max_examples=1000)
@given(text.filter(lambda s: s))
def test_escape_class_parses(s):
    sl = cp.CSSParser('.' + cp.escape(s)).process_selectors()
    assert sl.selectors[0].classes == (s,)
```

**Failing input**: `s='\x80'`

## Reproducing the Bug

```python
import soupsieve as sv

sv.compile('.' + sv.escape('\x80'))
# SelectorSyntaxError: Malformed class selector at position 0
```

## Why This Is A Bug

`soupsieve.escape` exists to make an arbitrary string usable as an identifier in a selector, and `css_unescape(escape(s)) == s` holds. Yet the parser can't read the escaped result. Under CSS Syntax Level 3, every code point >= U+0080 is a "non-ASCII ident code point", so the parser's `\x7B-\x9f` exclusion is too broad. A class/id containing U+0080–U+009F (e.g. from mis-decoded cp1252 text) can never be selected via `escape()`.

## Fix

```diff
 IDENTIFIER = fr'''
-(?:(?:-?(?:[^\x00-\x2f\x30-\x40\x5B-\x5E\x60\x7B-\x9f]|{CSS_ESCAPES})+|--)
-(?:[^\x00-\x2c\x2e\x2f\x3A-\x40\x5B-\x5E\x60\x7B-\x9f]|{CSS_ESCAPES})*)
+(?:(?:-?(?:[^\x00-\x2f\x30-\x40\x5B-\x5E\x60\x7B-\x7f]|{CSS_ESCAPES})+|--)
+(?:[^\x00-\x2c\x2e\x2f\x3A-\x40\x5B-\x5E\x60\x7B-\x7f]|{CSS_ESCAPES})*)
 '''
```

(Alternatively, have `escape()` hex-escape U+0080–U+009F so its output stays parseable.)

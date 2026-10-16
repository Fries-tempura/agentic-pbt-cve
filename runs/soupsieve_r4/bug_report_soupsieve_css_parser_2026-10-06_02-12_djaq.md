# Bug Report: soupsieve.css_parser escape() output for U+0080–U+009F cannot be parsed as an identifier

**Target**: `soupsieve.css_parser.escape` / `IDENTIFIER` pattern
**Severity**: Low
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`soupsieve.escape(ident)` leaves every code point ≥ 0x80 unescaped, which matches the CSSOM "serialize an identifier" algorithm. The parser's `IDENTIFIER` regex, however, excludes `\x80-\x9f` from identifier characters. So `sv.compile('#' + sv.escape(x))` raises `SelectorSyntaxError` for any `x` that contains a C1 control character.

## Property-Based Test

```python
@settings(max_examples=2000)
@given(st.text(min_size=1).filter(lambda t: '\x00' not in t and '\r' not in t and '\x0c' not in t))
def test_escape_round_trip(ident):
    esc = sv.escape(ident)
    sel = sv.compile('#' + esc)
    assert sel.selectors[0].ids == (ident,)
```

**Failing input**: `ident='\x80'`

## Reproducing the Bug

```python
import soupsieve as sv

sv.compile('#' + sv.escape('\x80'))
```

```
soupsieve.util.SelectorSyntaxError: Malformed id selector at position 0
```

## Why This Is A Bug

`escape` is documented as escaping an identifier so it can be used safely in a selector, so its output should always parse back to the same identifier. CSS Syntax Level 3 defines a "non-ASCII ident code point" as any code point ≥ U+0080, so U+0080–U+009F are legal unescaped identifier characters. The `IDENTIFIER` pattern's `\x7B-\x9f` exclusion range is wrong; it should stop at `\x7f`. I confirmed that the patch below makes `sv.select('#' + sv.escape('\x85x'), soup)` return the matching element.

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

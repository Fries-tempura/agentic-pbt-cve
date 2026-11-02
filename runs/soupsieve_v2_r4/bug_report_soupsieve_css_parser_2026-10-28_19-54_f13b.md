# Bug Report: soupsieve.css_parser escape() output for U+0080–U+009F is rejected by the parser

**Target**: `soupsieve.css_parser.escape` / `soupsieve.escape`
**Severity**: Low
**Bug Type**: Contract
**Date**: 2026-10-28

## Summary

`escape()` leaves characters U+0080–U+009F unescaped, but the parser's `IDENTIFIER` pattern rejects exactly that range. So `sv.compile('.' + sv.escape(x))` raises `SelectorSyntaxError` for any identifier containing one of these characters.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
import soupsieve as sv

idents = st.text(st.characters(codec='utf-8', exclude_categories=['Cs']), min_size=1, max_size=10)

@settings(max_examples=1000)
@given(idents)
def test_escape_roundtrip_selector(x):
    """CLAIM-2: '.' + escape(x) parses and yields class x."""
    sel = sv.compile('.' + sv.escape(x))
    assert sel.selectors[0].classes == (x.replace('\0', '�'),)
```

**Failing input**: `x='\x80'`

## Reproducing the Bug

```python
import soupsieve as sv

sv.compile('.' + sv.escape('\x80'))
```

This raises `SelectorSyntaxError: Malformed class selector at position 0`. By contrast, `sv.compile('.\\80 ')` (the hex-escaped form) parses fine.

## Why This Is A Bug

The API docs say `escape` "escapes any character that would normally cause an identifier to be invalid". The parser treats U+0080–U+009F as invalid in identifiers, yet `escape` does not escape them, so its output is not a usable identifier for soupsieve itself.

## Fix

```diff
--- a/soupsieve/css_parser.py
+++ b/soupsieve/css_parser.py
@@ def escape(ident: str) -> str:
             if codepoint == 0x00:
                 string.append('�')
-            elif (0x01 <= codepoint <= 0x1F) or codepoint == 0x7F:
+            elif (0x01 <= codepoint <= 0x1F) or (0x7F <= codepoint <= 0x9F):
                 string.append(f'\\{codepoint:x} ')
```

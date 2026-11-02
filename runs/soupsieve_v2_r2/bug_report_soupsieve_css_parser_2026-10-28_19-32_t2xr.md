# Bug Report: soupsieve.escape output for U+0080–U+009F is rejected by the selector parser

**Target**: `soupsieve.css_parser.escape` / `IDENTIFIER` pattern
**Severity**: Low
**Bug Type**: Contract
**Date**: 2026-10-28

## Summary

`escape()` leaves every code point ≥ 0x80 unescaped, but the parser's `IDENTIFIER` regex excludes `\x7B-\x9f` from identifier characters. An identifier that contains a C1 control character (U+0080–U+009F) therefore escapes to a string that `compile` rejects with `SelectorSyntaxError`.

## Property-Based Test

```python
@settings(max_examples=500)
@given(st.text(min_size=1).filter(lambda s: '\x00' not in s))
def test_escape_round_trip(s):
    """CLAIM-3: '.' + escape(s) parses back to class s."""
    sel = cp.CSSParser('.' + sv.escape(s)).process_selectors()
    assert sel.selectors[0].classes == (s,)
```

**Failing input**: `s='\x80'`

## Reproducing the Bug

```python
import soupsieve as sv

sv.compile("." + sv.escape("\x80"))
```

Result: `SelectorSyntaxError: Malformed class selector at position 0`. The same happens for every character from U+0080 to U+009F; U+00A0 and above work.

## Why This Is A Bug

`escape` exists so that any string can be embedded in a selector as an identifier. Its output should always be accepted by the library's own parser. Here the two halves of the library use different definitions of "identifier character". Such characters can turn up in class or id values that came from mis-decoded (cp1252/latin-1) documents.

## Fix

Make `escape` escape C1 controls the same way it escapes C0 controls. This matches how the parser's `IDENTIFIER` pattern treats them.

```diff
--- a/soupsieve/css_parser.py
+++ b/soupsieve/css_parser.py
@@ def escape(ident: str) -> str:
             if codepoint == 0x00:
                 string.append('\ufffd')
-            elif (0x01 <= codepoint <= 0x1F) or codepoint == 0x7F:
+            elif (0x01 <= codepoint <= 0x1F) or (0x7F <= codepoint <= 0x9F):
                 string.append(f'\\{codepoint:x} ')
```

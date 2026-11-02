# Bug Report: soupsieve.escape output for U+0080–U+009F is rejected by the selector parser

**Target**: `soupsieve.css_parser.escape` / `IDENTIFIER` pattern
**Severity**: Low
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`escape()` passes every code point ≥ U+0080 through unescaped, which matches the CSSOM "serialize an
identifier" algorithm. However, the parser's `IDENTIFIER` regex excludes `\x80-\x9f`, because it
uses `\x7B-\x9f` in its negated character classes. As a result, `sv.compile('.' + sv.escape(s))`
raises `SelectorSyntaxError` for any `s` containing a C1 control character (U+0080–U+009F). The
library's own escaper produces selectors that its parser cannot read.

## Property-Based Test

```python
@settings(max_examples=1000)
@given(s=st.text(min_size=1).filter(lambda s: '\x00' not in s))
def test_escape_round_trip(s):
    """CLAIM-3: compile('.' + escape(s)) yields class s."""
    sel = sv.compile('.' + cp.escape(s)).selectors[0]
    assert sel.classes == (s,)
```

**Failing input**: `s='\x80'`

## Reproducing the Bug

```python
import soupsieve as sv

sv.compile('.' + sv.escape('\x80'))
```

```
soupsieve.util.SelectorSyntaxError: Malformed class selector at position 0
```

## Why This Is A Bug

The only purpose of `soupsieve.escape` ("Escape CSS identifier") is to turn an arbitrary string into
an identifier that can be put into a selector. CSS Syntax Level 3 defines a non-ASCII ident code point
as anything ≥ U+0080, so `\x80` is a valid identifier character. The parser is wrong to reject it,
and the escape/parse round trip breaks for those 32 code points.

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

Alternatively, if the parser deliberately excludes C1 controls, `escape()` should hex-escape U+0080–U+009F
the way it already escapes U+0001–U+001F and U+007F.

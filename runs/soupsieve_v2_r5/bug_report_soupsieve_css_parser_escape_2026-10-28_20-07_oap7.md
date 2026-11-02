# Bug Report: soupsieve.escape output is rejected by soupsieve for U+0080–U+009F

**Target**: `soupsieve.css_parser.escape`
**Severity**: Low
**Bug Type**: Contract
**Date**: 2026-10-28

## Summary

`escape()` leaves every code point ≥ 0x80 unescaped. The parser's `IDENTIFIER` pattern, however, excludes `\x7B-\x9f`. So when an identifier contains a C1 control character, the result of `escape()` cannot be used in a selector.

## Property-Based Test

```python
@given(st.text(min_size=1).filter(lambda s: '\x00' not in s))
def test_escape_round_trip(s):
    """CLAIM-3: '.' + escape(s) parses to a class selector named s."""
    sl = CSSParser('.' + escape(s)).process_selectors()
    assert len(sl) == 1
    assert sl[0].classes == (s,)
```

**Failing input**: `s='\x80'`

## Reproducing the Bug

```python
import soupsieve as sv
sv.compile('.' + sv.escape('\x80'))
```

`SelectorSyntaxError: Malformed class selector at position 0`

## Why This Is A Bug

`escape` exists so that arbitrary identifiers can be embedded in selectors. With the U+0080–U+009F range excluded, 2000 examples of the round trip all pass, so this range is the only gap.

## Fix

Make `escape` hex-escape the C1 range in the same way it escapes C0:

```diff
-            elif (0x01 <= codepoint <= 0x1F) or codepoint == 0x7F:
+            elif (0x01 <= codepoint <= 0x1F) or (0x7F <= codepoint <= 0x9F):
                 string.append(f'\\{codepoint:x} ')
```

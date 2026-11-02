# Bug Report: soupsieve.css_parser css_unescape crashes on hex escapes above U+10FFFF

**Target**: `soupsieve.css_parser.css_unescape`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

The tokenizer accepts any 1–6 digit hex escape, but `css_unescape` passes the value straight to `chr()`. A selector such as `.\110000` therefore raises a bare `ValueError` instead of returning a result or raising `SelectorSyntaxError`.

## Property-Based Test

```python
@given(st.integers(min_value=1, max_value=0xFFFFFF))
def test_compile_hex_escape_no_crash(cp_):
    """CLAIM-2: an accepted escaped class selector compiles or raises SelectorSyntaxError."""
    try:
        sv.compile('.\\%x' % cp_)
    except SelectorSyntaxError:
        pass
```

**Failing input**: `cp_=1114112` (0x110000)

## Reproducing the Bug

```python
import soupsieve as sv
sv.compile(r'.\110000')
```

`ValueError: chr() arg not in range(0x110000)`

## Why This Is A Bug

CSS Syntax 3 §4.3.7 says that an escaped code point which is zero, a surrogate, or greater than U+10FFFF becomes U+FFFD. The code already handles the zero case (`if codepoint == 0`) but misses the out-of-range case. Code that compiles untrusted selectors and catches `SelectorSyntaxError` will be hit by this undocumented exception.

## Fix

```diff
             codepoint = int(m.group(1)[1:], 16)
-            if codepoint == 0:
+            if codepoint == 0 or codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
                 codepoint = UNICODE_REPLACEMENT_CHAR
```

# Bug Report: soupsieve.css_parser Out-of-range hex escapes crash compile with ValueError from chr()

**Target**: `soupsieve.css_parser.css_unescape`
**Severity**: Low
**Bug Type**: Crash
**Date**: 2026-10-06

## Summary

A CSS hex escape whose value is above U+10FFFF, such as `\110000` or `\FFFFFF`, makes `css_unescape` call `chr()` with an invalid code point. This raises a raw `ValueError: chr() arg not in range(0x110000)` from `soupsieve.compile`.

## Property-Based Test

```python
@given(st.integers(min_value=1, max_value=0xFFFFFF))
def test_hex_escape_never_crashes(cpnt):
    try:
        sv.compile('#\\%x ' % cpnt)
    except SelectorSyntaxError:
        pass
```

**Failing input**: `cpnt=1114112` (0x110000). The generic fuzz test also found it with `s='\\110000'`.

## Reproducing the Bug

```python
import soupsieve as sv

sv.compile(r'#\110000')
```

## Why This Is A Bug

CSS Syntax Level 3 §4.3.7 ("consume an escaped code point") says that if the hex value is 0, a surrogate, or greater than the maximum allowed code point, the result is U+FFFD REPLACEMENT CHARACTER. `css_unescape` already does this for 0 but not for values above 0x10FFFF. The input is a valid CSS escape, so it should parse to U+FFFD and not crash.

## Fix

```diff
--- a/soupsieve/css_parser.py
+++ b/soupsieve/css_parser.py
@@ def css_unescape(content: str, string: bool = False) -> str:
         if m.group(1):
             codepoint = int(m.group(1)[1:], 16)
-            if codepoint == 0:
+            if codepoint == 0 or codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
                 codepoint = UNICODE_REPLACEMENT_CHAR
             value = chr(codepoint)
```

# Bug Report: soupsieve.css_parser `css_unescape` crashes on escapes above U+10FFFF

**Target**: `soupsieve.css_parser.css_unescape`
**Severity**: Low
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

The tokenizer accepts any 1–6 hex digit escape, but `css_unescape` passes the value straight to `chr()`. Escapes such as `\110000` or `\FFFFFF` therefore raise `ValueError: chr() arg not in range(0x110000)` and compilation fails.

## Property-Based Test

```python
@given(st.integers(min_value=0x110000, max_value=0xFFFFFF), st.sampled_from(['.{}', '#{}', '[x="{}"]', ':lang("{}")']))
def test_large_codepoint_escape(cp_, tmpl):
    """CLAIM-6: escapes above U+10FFFF decode to U+FFFD, no chr() crash."""
    sv.compile(tmpl.format(f'\\{cp_:x}'))
```

**Failing input**: `cp_=1114112` (0x110000), `tmpl='.{}'`

## Reproducing the Bug

```python
import soupsieve as sv
sv.compile(r'.\110000')
```

## Why This Is A Bug

CSS Syntax 3 §4.3.7 says that an escape whose value is 0, a surrogate, or greater than U+10FFFF is replaced with U+FFFD. The function already handles the 0 case, but not the other two. The result is an internal `chr()` error instead of either a valid selector or a `SelectorSyntaxError`.

## Fix

```diff
             codepoint = int(m.group(1)[1:], 16)
-            if codepoint == 0:
+            if codepoint == 0 or codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
                 codepoint = UNICODE_REPLACEMENT_CHAR
```

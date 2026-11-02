# Bug Report: soupsieve.css_parser css_unescape crashes on out-of-range hex escapes

**Target**: `soupsieve.css_parser.css_unescape` (via `soupsieve.compile`)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

The tokenizer accepts any CSS hex escape of 1–6 digits (`\\[a-f0-9]{1,6}`). However, `css_unescape`
passes the value straight to `chr()`. Any escape above `\10FFFF` therefore raises a bare
`ValueError: chr() arg not in range(0x110000)` from inside `compile`. This affects identifiers,
classes, ids, attribute names and quoted attribute values.

## Property-Based Test

```python
@settings(max_examples=300)
@given(cp_=st.integers(min_value=0, max_value=0xFFFFFF))
def test_hex_escape_never_raises(cp_):
    """CLAIM-2: any 1-6 hex digit escape is unescaped without raising."""
    esc = '\\' + format(cp_, 'x')
    out = cp.css_unescape(esc)
    if cp_ > 0x10FFFF:
        assert out == '�'
    sv.compile('.a' + esc + ' ')
```

**Failing input**: `cp_=1114112` (i.e. `\110000`)

## Reproducing the Bug

```python
import soupsieve as sv

sv.compile(r'.a\110000')
```

```
ValueError: chr() arg not in range(0x110000)
```

## Why This Is A Bug

The selector is valid CSS. CSS Syntax Level 3 §4.3.7 ("consume an escaped code point") says: "If
this number is zero, or is for a surrogate, or is greater than the maximum allowed code point,
return U+FFFD". The code already applies the zero case (`if codepoint == 0: codepoint =
UNICODE_REPLACEMENT_CHAR`) but omits the other two. The out-of-range case is a crash. The surrogate
case (`\D800`) silently produces a lone surrogate instead of U+FFFD.

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

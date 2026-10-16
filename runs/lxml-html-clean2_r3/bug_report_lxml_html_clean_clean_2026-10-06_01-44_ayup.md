# Bug Report: lxml_html_clean.clean crashes on numeric character references to control characters

**Target**: `lxml_html_clean.clean` (`clean_html`, `fromstring`)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-06

## Summary

`fromstring` strips raw ASCII control characters before parsing, but it does not handle numeric character references such as `&#1;` / `&#x1;`. libxml2 decodes those into real control characters in the tree. When the cleaner then calls `drop_tag()` (for `<blink>`, `<marquee>`, `<form>`, `<iframe>`, `<head>`, …), lxml concatenates the tail text into the parent and rejects the control character with `ValueError`.

## Property-Based Test

```python
@settings(max_examples=2000, suppress_health_check=list(HealthCheck), deadline=None)
@given(html_doc)   # grammar-generated HTML fragments, see test_clean.py
def test_style_kept_clean_removes_js(s):
    c = Cleaner(safe_attrs_only=False, style=False, inline_style=False, links=False)
    try:
        out = c.clean_html(s)
    except etree.ParserError:
        return
    check(out)
```

**Failing input**: `'<iframe ></iframe>&#1;javascript:1'` (the default `clean_html` also fails, e.g. on `'javascript:alert(1)<!--javascript:alert(1)-->&#1;javascript:1'`)

## Reproducing the Bug

```python
from lxml_html_clean import clean_html

clean_html("<div><blink>hi</blink>&#1;there</div>")
```

```
  File ".../lxml_html_clean/clean.py", line 455, in __call__
    _remove.pop().drop_tag()
  File ".../lxml/html/__init__.py", line 355, in drop_tag
    parent.text = (parent.text or '') + self.tail
ValueError: All strings must be XML compatible: Unicode or ASCII, no NULL bytes or control characters
```

## Why This Is A Bug

The library already treats control characters in input as something to strip silently (`fromstring` docstring: "removes ASCII control chars before passing the input to … lxml.html.fromstring"). The same characters written as entities get through and crash the sanitizer. Whether it crashes depends on unrelated details, like whether a removable tag happens to sit next to the entity. Any user who can submit HTML can trigger the exception. The same input without a dropped tag cleans "successfully" but outputs raw control characters (e.g. `clean_html("<p>&#1;</p>") == "<p>\x01</p>"`), which is inconsistent with the stripping of literal control chars.

## Fix

Strip numeric character references that decode to the same control-character set before parsing. (An alternative is to walk the parsed tree and scrub `.text` / `.tail` / attribute values.)

```diff
--- a/lxml_html_clean/clean.py
+++ b/lxml_html_clean/clean.py
@@ -92,16 +92,28 @@
 # - 0D - Carriage Return
 _ascii_control_characters_str = re.compile("[\x00-\x08\x0C\x0E-\x1F\x7F]")
 _ascii_control_characters_bytes = re.compile(b"[\x00-\x08\x0C\x0E-\x1F\x7F]")
+_numeric_char_ref_str = re.compile(r"&#(?:[xX]([0-9a-fA-F]+)|([0-9]+));?")
+_numeric_char_ref_bytes = re.compile(rb"&#(?:[xX]([0-9a-fA-F]+)|([0-9]+));?")
+
+
+def _drop_control_char_ref(match):
+    hex_value, dec_value = match.groups()
+    code = int(hex_value, 16) if hex_value else int(dec_value)
+    if code < 0x110000 and _ascii_control_characters_str.match(chr(code)):
+        return match.group(0)[:0]
+    return match.group(0)
 
 
 def fromstring(data):
     """
     Enhanced fromstring function that removes ASCII control chars
     before passing the input to the original lxml.html.fromstring.
     """
     if isinstance(data, bytes):
+        data = _numeric_char_ref_bytes.sub(_drop_control_char_ref, data)
         return lxml_fromstring(_ascii_control_characters_bytes.sub(b"", data))
     else:
+        data = _numeric_char_ref_str.sub(_drop_control_char_ref, data)
         return lxml_fromstring(_ascii_control_characters_str.sub("", data))
 
 
```

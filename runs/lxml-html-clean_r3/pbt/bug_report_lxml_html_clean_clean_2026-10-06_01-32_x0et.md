# Bug Report: lxml_html_clean.clean ValueError on control-character references inside removed tags

**Target**: `lxml_html_clean.clean` (`Cleaner.__call__` / `clean_html`)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-06

## Summary

`clean_html` crashes with `ValueError: All strings must be XML compatible` when a tag that gets "removed" (e.g. `<blink>`, `<title>`, `<marquee>`, `<iframe>`, `<form>`) contains a numeric character reference to a C0 control character, such as `&#1;`.

## Property-Based Test

```python
@settings(max_examples=3000, suppress_health_check=list(HealthCheck), deadline=None)
@given(docs)   # random HTML fragments, see pbt/test_clean.py
def test_output_safe_after_reparse(h):
    out = safe_clean(h)          # clean_html(h), tolerating only etree.ParserError
    if out is None:
        return
    check_safe(out)
```

**Failing input**: `'<title><div href="javascript:alert(1)" href="&#1;javascript:alert(1)">'`, minimized to `'<title>&#1;</title>'`

## Reproducing the Bug

```python
from lxml_html_clean import clean_html

clean_html('<div><blink>&#1;</blink></div>')
clean_html('<title>&#1;</title>')
```

Both raise:
```
ValueError: All strings must be XML compatible: Unicode or ASCII, no NULL bytes or control characters
```
from `lxml/html/__init__.py` `drop_tag` (`parent.text = (parent.text or '') + self.text`).

## Why This Is A Bug

The module's `fromstring` claims to remove ASCII control characters before parsing, but it only removes raw ones. The HTML parser decodes references such as `&#1;` back into `\x01` in text and attributes. When the cleaner calls `drop_tag()` on a removed tag, lxml merges that text into the parent through the `.text` setter, and the setter rejects control characters. So a short, attacker-controlled input crashes the sanitizer, which callers usually do not expect (it is not a `ParserError`). Inputs where the element is not removed (e.g. `<p>&#1;</p>`) are passed through with a raw `\x01` in the output instead. The same root cause makes the cleaner non-idempotent: `clean_html('<div title="&#1;javascript:alert(1)">')` returns `<div title="\x01javascript:alert(1)"></div>`, and cleaning that again strips the `\x01`.

## Fix

After parsing, strip control characters from text, tail and attribute values as well, not only from the raw input string. For example, in `Cleaner.__call__` before the tag-removal phase:

```diff
+        for el in doc.iter():
+            if el.text and _ascii_control_characters_str.search(el.text):
+                el.text = _ascii_control_characters_str.sub('', el.text)
+            if el.tail and _ascii_control_characters_str.search(el.tail):
+                el.tail = _ascii_control_characters_str.sub('', el.tail)
+            if isinstance(el.tag, str):
+                for k, v in el.attrib.items():
+                    if _ascii_control_characters_str.search(v):
+                        el.set(k, _ascii_control_characters_str.sub('', v))
```

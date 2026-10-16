# Bug Report: lxml_html_clean.clean crashes when the root element is a killed tag containing other killed/removed nodes

**Target**: `lxml_html_clean.clean` (`Cleaner.__call__`, `clean_html`)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-06

## Summary

If the parsed fragment's root is a tag that gets *killed* (e.g. `<button>`, `<select>`, `<textarea>`, `<input>`, `<script>`) and its subtree contains another node that is also queued for kill/removal (a comment, `<iframe>`, `<script>`, `<blink>` …), `clean_html` raises `AssertionError` from `lxml.html.HtmlElement.drop_tree` / `drop_tag`.

## Property-Based Test

```python
@settings(max_examples=3000, suppress_health_check=list(HealthCheck), deadline=None)
@given(html_doc)   # grammar-generated HTML fragments, see test_clean.py
def test_default_clean_removes_js(s):
    try:
        out = clean_html(s)
    except etree.ParserError:
        return
    check(out)     # no <script>, no on* attrs, no javascript: URLs
```

**Failing input**: `'<button ><!--javascript:alert(1)-->'` and `'<button ><iframe >'`

## Reproducing the Bug

```python
from lxml_html_clean import clean_html

clean_html("<button>Click <!-- note --></button>")
clean_html("<select><option>a</option><blink>b</blink></select>")
```

```
  File ".../lxml_html_clean/clean.py", line 452, in __call__
    _kill.popleft().drop_tree()
  File ".../lxml/html/__init__.py", line 320, in drop_tree
    assert parent is not None
AssertionError
```

## Why This Is A Bug

`clean_html` is the library's main entry point for untrusted HTML, and these inputs are ordinary fragments. When the root is in `_kill`, the code takes the special path `el.clear()`. That detaches every descendant, but descendants that were already collected in `_kill` / `_remove` stay queued. Later `drop_tree()` / `drop_tag()` calls on those detached nodes hit `assert parent is not None`. A sanitizer that throws on attacker-chosen input breaks any caller that doesn't wrap it in a try/except. Under `python -O` the assertion is skipped and the failure becomes an `AttributeError` on `None` instead.

## Fix

```diff
--- a/lxml_html_clean/clean.py
+++ b/lxml_html_clean/clean.py
@@ -447,6 +447,9 @@
             if el.tag != 'html':
                 el.tag = 'div'
             el.clear()
+            # descendants were removed together with the root's content
+            _kill.clear()
+            _remove.clear()
 
         while _kill:
             _kill.popleft().drop_tree()  # popleft to start with innermost elements
```

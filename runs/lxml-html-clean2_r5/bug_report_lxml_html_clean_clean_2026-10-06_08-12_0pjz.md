# Bug Report: lxml_html_clean.clean AssertionError when the root element is killed and has killable descendants

**Target**: `lxml_html_clean.clean.Cleaner.__call__` / `clean_html`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-06

## Summary

If the root element of the document is a tag that gets *killed* (e.g. `<button>`, `<applet>`, or anything in `kill_tags`), and it contains another killable node (`<script>`, `<input>`, a comment, ...), `Cleaner.__call__` crashes with a bare `AssertionError` from `lxml.html.HtmlElement.drop_tree`.

## Property-Based Test

```python
@settings(max_examples=2000, suppress_health_check=list(HealthCheck), deadline=None)
@given(html_docs)   # random nested HTML fragments built from common/dangerous tags and attributes
def test_default_clean_is_safe(html):
    try:
        out = clean_html(html)
    except (etree.ParserError, ValueError):
        return
    check_safe(out)
```

**Failing input**: `html='<button><script></script></button>'`

## Reproducing the Bug

```python
from lxml_html_clean import clean_html

clean_html('<button>Click<!-- note --></button>')
```

```
AssertionError
  File ".../lxml/html/__init__.py", line 320, in drop_tree
    assert parent is not None
```

Other failing inputs: `<button><script>x</script></button>`, `<button><input></button>`, `<applet><link></applet>`, and `Cleaner(kill_tags=['div'])` on `<div><!--c--></div>`.

## Why This Is A Bug

`clean_html` is meant to accept arbitrary (untrusted) HTML and return a sanitized version. It already has a dedicated branch for "the root element must be killed" (`_kill[0] == doc`), which clears the root instead of dropping it. But `el.clear()` detaches every descendant, while those descendants are still queued in `_kill`. The loop then calls `drop_tree()` on detached elements whose parent is `None`, and lxml's assertion fails. Any user content that is a single `<button>` holding a comment or script makes the sanitizer raise instead of returning output. The same input nested inside a `<div>` cleans without error.

## Fix

After the root is cleared, every other queued element is a detached descendant, so there's nothing left to process:

```diff
--- a/lxml_html_clean/clean.py
+++ b/lxml_html_clean/clean.py
@@ -446,7 +446,10 @@ class Cleaner:
             el = _kill.popleft()
             if el.tag != 'html':
                 el.tag = 'div'
             el.clear()
+            # all remaining queued elements were descendants of the root and are now detached
+            _kill.clear()
+            _remove.clear()
 
         while _kill:
             _kill.popleft().drop_tree()  # popleft to start with innermost elements
```

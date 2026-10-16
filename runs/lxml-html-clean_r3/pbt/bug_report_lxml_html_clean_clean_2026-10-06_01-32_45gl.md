# Bug Report: lxml_html_clean.clean AssertionError when the root element is killed and has killed/removed descendants

**Target**: `lxml_html_clean.clean` (`Cleaner.__call__`)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-06

## Summary

If the root element of the document is a tag the cleaner kills (e.g. `<select>`, `<button>`, `<applet>`, `<input>`), and it contains a comment or another killed/removed element, `clean_html` raises a bare `AssertionError` from lxml's `drop_tree`/`drop_tag`.

## Property-Based Test

```python
@settings(max_examples=3000, suppress_health_check=list(HealthCheck), deadline=None)
@given(docs)   # random HTML fragments built from tags/attrs/payloads, see pbt/test_clean.py
def test_output_safe_after_reparse(h):
    out = safe_clean(h)          # clean_html(h), tolerating only etree.ParserError
    if out is None:
        return
    check_safe(out)
```

**Failing input**: `'<applet><!-- c -->'` (also `'<applet><iframe>'`)

## Reproducing the Bug

```python
from lxml_html_clean import clean_html

clean_html('<select><option>A</option><!-- note --></select>')
clean_html('<button><span>x</span><!-- c --></button>')
clean_html('<applet><iframe>')
```

All three raise `AssertionError` (at `lxml/html/__init__.py` `assert parent is not None`).

## Why This Is A Bug

These are ordinary HTML fragments, and the cleaner already has a special case for "the root itself is to be killed". It handles that case by calling `el.clear()` on the root, which detaches every descendant. But the descendants already queued in `_kill`/`_remove` are not dropped from the queues. The loops that follow then call `drop_tree()`/`drop_tag()` on elements that no longer have a parent, and lxml's assertion fails. A sanitizer should not crash on valid input.

## Fix

```diff
         elif _kill and _kill[0] == doc:
             # We have to drop the parent-most element, which we can't
             # do.  Instead we'll clear it:
             el = _kill.popleft()
             if el.tag != 'html':
                 el.tag = 'div'
             el.clear()
+            # clear() detached all descendants; nothing left to kill/remove
+            _kill.clear()
+            _remove.clear()
```

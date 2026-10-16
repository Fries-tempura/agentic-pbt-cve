# Bug Report: lxml_html_clean.clean crashes when the root element is killed and has killable/removable descendants

**Target**: `lxml_html_clean.clean` (`Cleaner.__call__` / `clean_html`)
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-05

## Summary

When the parsed fragment's root element is a tag the cleaner kills (e.g. `<button>`, `<input>`, `<textarea>`, `<select>`, `<script>`), and it contains another element that is also scheduled to be killed or removed (e.g. `<script>`, `<iframe>`), `clean_html` raises `AssertionError` instead of returning cleaned HTML.

## Property-Based Test

```python
@settings(max_examples=3000, suppress_health_check=list(HealthCheck), deadline=None)
@given(st.lists(html_doc(), min_size=1, max_size=3).map("".join))
def test_default_clean_removes_dangerous_content(html):
    out = clean_html(html)
    check_output(out)
```

(`html_doc` generates nested HTML fragments from a pool of tags, including `button`, `script`, `iframe`, `select`, and attributes. See `test_clean_pbt.py`.)

**Failing input**: `'<button><iframe></iframe></button>'` (also `'<button><script>alert(1)</script></button>'`; with `Cleaner(safe_attrs_only=False)`: `'<select><iframe></iframe></select>'`)

## Reproducing the Bug

```python
from lxml_html_clean import clean_html

clean_html('<button><script>alert(1)</script></button>')
```

```
  File ".../lxml_html_clean/clean.py", line 452, in __call__
    _kill.popleft().drop_tree()
  File ".../lxml/html/__init__.py", line 320, in drop_tree
    assert parent is not None
AssertionError
```

## Why This Is A Bug

`clean_html` is meant to sanitize arbitrary, untrusted HTML. A short user-supplied fragment like `<button><script>…</script></button>` makes it crash instead of returning sanitized output, so any app that cleans user input hits an unhandled exception (a cheap way to trigger errors or DoS). The code already tries to handle a killed root: it turns it into an empty `<div>`, and `<button><b>x</b></button>` does return `<div></div>`. But `el.clear()` detaches every descendant while those descendants are still queued in `_kill` / `_remove`. When the loop later calls `drop_tree()` / `drop_tag()` on them, they have no parent. Running Python with `-O` changes the error to an `AttributeError` (`None.remove`), but it still crashes.

## Fix

Every other queued element descends from the root, and `el.clear()` has already detached them, so the queues can be emptied:

```diff
--- a/lxml_html_clean/clean.py
+++ b/lxml_html_clean/clean.py
@@ -446,6 +446,9 @@ class Cleaner:
             el = _kill.popleft()
             if el.tag != 'html':
                 el.tag = 'div'
             el.clear()
+            # All remaining queued elements were descendants and are now detached
+            _kill.clear()
+            _remove.clear()
 
         while _kill:
             _kill.popleft().drop_tree()  # popleft to start with innermost elements
```

I checked this patch by monkeypatching it in: all three failing inputs return `'<div></div>'`.

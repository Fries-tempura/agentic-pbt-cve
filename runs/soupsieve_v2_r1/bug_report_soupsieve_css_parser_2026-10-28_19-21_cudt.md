# Bug Report: soupsieve.css_parser `[attr=value]` / `[attr$=value]` match values with an extra trailing newline

**Target**: `soupsieve.css_parser.CSSParser.parse_attribute_selector`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

The attribute patterns end in `$` (`r'^%s$'` for `=`, `r'.*?%s$'` for `$=`, `r'^%s(?:-.*)?$'` for `|=`). In Python, `$` also matches just before a final `\n`, so `[x="foo"]` matches an element whose `x` attribute is `"foo\n"`.

## Property-Based Test

```python
@given(st.text(alphabet='abc', min_size=1, max_size=5), st.sampled_from(['=', '$=']))
def test_attr_exact_no_trailing_newline(v, op):
    """CLAIM-3: [x="v"] / [x$="v"] must not match x == v + '\\n'."""
    soup = BeautifulSoup('<div></div>', 'html.parser')
    soup.div['x'] = v + '\n'
    assert sv.select(f'div[x{op}"{v}"]', soup) == []
```

**Failing input**: `v='a', op='='`

## Reproducing the Bug

```python
from bs4 import BeautifulSoup
import soupsieve as sv

soup = BeautifulSoup('<div x="foo\n"></div>', 'html.parser')
print(sv.select('div[x="foo"]', soup))
print(sv.select('div[x$="foo"]', soup))
print(sv.select('div[x|="foo"]', soup))
```

All three print the `div`.

## Why This Is A Bug

The comment at the `=` branch says "Value matches", and CSS Selectors 4 defines `[att=val]` as an exact match. `"foo\n"` is not equal to `"foo"`, does not end with `"foo"`, and is not `"foo"` or `"foo-..."`. Attribute values that contain newlines are legal HTML, and selectors are often used for filtering or sanitising, so false positives matter.

## Fix

```diff
-            pattern = re.compile(r'.*?%s$' % re.escape(value), flags)
+            pattern = re.compile(r'.*?%s\Z' % re.escape(value), flags)
@@
-            pattern = re.compile(r'^%s(?:-.*)?$' % re.escape(value), flags)
+            pattern = re.compile(r'^%s(?:-.*)?\Z' % re.escape(value), flags)
@@
-            pattern = re.compile(r'^%s$' % re.escape(value), flags)
+            pattern = re.compile(r'^%s\Z' % re.escape(value), flags)
```

(The `~=` lookahead `(?=(?:[ \t\r\n\f]|$))` is not affected, because a trailing newline there is already a valid separator.)

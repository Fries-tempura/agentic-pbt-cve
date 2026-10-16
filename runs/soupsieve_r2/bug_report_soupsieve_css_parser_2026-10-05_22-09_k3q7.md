# Bug Report: soupsieve.css_parser `:-soup-contains()` unescapes its argument twice

**Target**: `soupsieve.css_parser.CSSParser.parse_pseudo_contains`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`parse_pseudo_contains` runs `css_unescape` over the whole argument list, then tokenizes it, then unescapes each value again. Escapes get applied twice, so escaped quotes, backslashes or control characters change the meaning of the selector. For example, `:-soup-contains("\22")` ends up matching every element.

## Property-Based Test

```python
@settings(max_examples=1000)
@given(st.text(st.characters(blacklist_categories=('Cs',)), min_size=1))
def test_contains_string_roundtrip(s):
    s = s.replace('\x00', '�')
    esc = ''.join(f'\\{ord(c):x} ' for c in s)
    sel = cp.CSSParser(f':-soup-contains("{esc}")').process_selectors()
    assert list(sel[0].contains[0].text) == [s]
```

**Failing input**: `s='\r'` (the parser returns `[]` instead of `['\r']`). The same test passes for `:lang()`, which does not do the extra unescape.

## Reproducing the Bug

```python
import soupsieve as sv
from bs4 import BeautifulSoup

soup = BeautifulSoup(r'<p>\41</p><p>A</p><p>say "hi"</p>', 'html.parser')
print(sv.select(r'p:-soup-contains("\5c 41")', soup))  # [<p>A</p>]; expected [<p>\41</p>]
print(sv.select(r'p:-soup-contains("\22")', soup))     # all 3 <p>; expected [<p>say "hi"</p>]
```

## Why This Is A Bug

In CSS, `"\5c 41"` is the string `\41` and `"\22"` is the string `"`. After the first unescape, the second pass sees `"\41"` (which becomes `A`) and `"""` (which tokenizes as an empty string, and an empty string matches everything). This breaks CSS string semantics. It also differs from `:lang()`, which parses the same `VALUE` grammar correctly.

## Fix

```diff
-        values = css_unescape(m.group('values'))
+        values = m.group('values')
```

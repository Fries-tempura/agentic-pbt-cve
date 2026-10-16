# Bug Report: soupsieve.css_parser `:-soup-contains()` unescapes its argument twice

**Target**: `soupsieve.css_parser.CSSParser.parse_pseudo_contains`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`parse_pseudo_contains` runs `css_unescape` on the whole argument list, then tokenizes it and runs `css_unescape` again on each value. So escapes are processed twice. An escaped backslash (`\\`) becomes a new escape sequence, and an escaped quote (`\"`) ends the string early and splits it into several values. `:-soup-contains()` then matches the wrong text. `:lang()`, which shares the same value grammar, unescapes only once and works correctly.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
import soupsieve as sv
from bs4 import BeautifulSoup

text = st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"), min_size=1)

@settings(max_examples=500)
@given(text)
def test_contains_value(s):
    soup = BeautifulSoup('<div></div>', 'html.parser')
    soup.div.string = s
    sel = 'div:-soup-contains("' + ''.join('\\' + format(ord(c), 'x') + ' ' for c in s) + '")'
    assert sv.select_one(sel, soup) is soup.div
```

**Failing input**: `s='\\'` (selector `div:-soup-contains("\5c ")`)

## Reproducing the Bug

```python
import soupsieve as sv
from bs4 import BeautifulSoup

soup = BeautifulSoup('<div>a\\b</div><p>x</p>', 'html.parser')

assert sv.select(r'div:-soup-contains("a\\b")', soup) == []
print(sv.compile(r'div:-soup-contains("a\\b")').selectors[0].contains)
# SelectorContains(text=('a\x0b',), own=False)

print(sv.compile(r'p:-soup-contains("x\"y")').selectors[0].contains)
# SelectorContains(text=('x', 'y'), own=False)
print(sv.select(r'p:-soup-contains("x\"y")', soup))
# [<p>x</p>]  -- matches although the text does not contain 'x"y'
```

## Why This Is A Bug

In CSS, `"a\\b"` is the string `a\b`, and `"x\"y"` is the single string `x"y`. Soup Sieve searches for `a<U+000B>` in the first case. In the second it searches for `x` OR `y`, which gives false-positive matches. There is no way to search for text containing a literal backslash. The sibling `:lang()` parser handles the same input correctly, which confirms that the single unescape is the intended behaviour.

## Fix

```diff
--- a/soupsieve/css_parser.py
+++ b/soupsieve/css_parser.py
@@ def parse_pseudo_contains(self, sel: _Selector, m: Match[str], has_selector: bool) -> bool:
         contains_own = pseudo == ":-soup-contains-own"
-        values = css_unescape(m.group('values'))
+        values = m.group('values')
         patterns = []
```

# Bug Report: soupsieve.css_parser `:-soup-contains()` unescapes its argument twice

**Target**: `soupsieve.css_parser.CSSParser.parse_pseudo_contains`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`parse_pseudo_contains` calls `css_unescape` on the whole raw argument list (`values = css_unescape(m.group('values'))`), then tokenises the result and unescapes each value a second time. Any text containing a backslash escape gets decoded twice. The search string ends up wrong, or vanishes completely. `:lang()`, whose code is otherwise identical, does not do this.

## Property-Based Test

```python
str_text = st.text(alphabet=st.sampled_from('ab09\\ f'), min_size=1, max_size=8).filter(lambda s: not s.endswith('\\'))

@given(str_text)
@settings(max_examples=500)
def test_contains_single_unescape(s):
    """CLAIM-2: :-soup-contains("S") stores css_unescape(S, True), like :lang."""
    s = s.replace('"', '')
    contains = cp.CSSParser(f':-soup-contains("{s}")').process_selectors()[0].contains[0].text
    lang = cp.CSSParser(f':lang("{s}")').process_selectors()[0].lang[0].languages
    assert lang == (cp.css_unescape(s, True),)
    assert contains == (cp.css_unescape(s, True),)
```

**Failing input**: `s='\\a'` (CSS `"\a"`, i.e. a newline): `:lang` stores `('\n',)` but `:-soup-contains` stores `()`, so the value disappears entirely.

## Reproducing the Bug

```python
from bs4 import BeautifulSoup
import soupsieve as sv
from soupsieve import css_parser as cp

print(cp.CSSParser(r'p:-soup-contains("a\\b")').process_selectors()[0].contains[0].text)
soup = BeautifulSoup(r'<p>a\b</p>', 'html.parser')
print(sv.select(r'p:-soup-contains("a\\b")', soup))
print(sv.select(r'p:-soup-contains("a\5c b")', soup))
```

Output: `('a\x0b',)`, `[]`, `[]`. The CSS string `"a\\b"` means the text `a\b`. The first pass turns it into `"a\b"` and the second pass decodes `\b` as the hex escape U+000B. Neither spelling can match a literal backslash.

## Why This Is A Bug

A CSS string token is unescaped exactly once. The per-token code already does that (`css_unescape(value[1:-1], True)`), and so does `:lang()` with the same structure. With the extra pass, `:-soup-contains` can't search for text that contains a backslash, and escapes such as `\a` (newline) or `\"` break the token so that values silently drop out of the list.

## Fix

```diff
         contains_own = pseudo == ":-soup-contains-own"
-        values = css_unescape(m.group('values'))
+        values = m.group('values')
         patterns = []
```

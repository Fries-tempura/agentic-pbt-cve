# Bug Report: black.strings.str_width ASCII fast path disagrees with char_width for control characters

**Target**: `black.strings.str_width`
**Severity**: Low
**Bug Type**: Contract
**Date**: 2026-10-06

## Summary

`char_width` says control characters have width 0, and it does return 0 for ASCII control characters. But `str_width` has a fast path for pure-ASCII strings that returns `len(line_str)`, so it counts each control character as 1. A string's width therefore depends on whether it happens to contain a non-ASCII character. `count_chars_in_width` also disagrees with `str_width`.

## Property-Based Test

```python
from hypothesis import given, strategies as st
from black.strings import str_width, char_width

@given(st.text())
def test_width(s):
    assert str_width(s) == sum(char_width(c) for c in s)
```

**Failing input**: `s='\x1f'`

## Reproducing the Bug

```python
from black.strings import str_width, char_width, count_chars_in_width

assert char_width("\x1f") == 0
print(str_width("\x1f"))
print(str_width("\x1fé"))
print(str_width(count_chars_in_width("\x1f", 0) * "\x1f"))
```

Output: `str_width("\x1f")` is `1`, while `str_width("\x1fé")` is also `1` (`\x1f` counts as 0 and `é` as 1). `count_chars_in_width("\x1f", 0)` returns 1, a prefix whose `str_width` is 1, which is more than the `max_width` of 0.

## Why This Is A Bug

`char_width`'s docstring says "control characters are counted as 0", and `str_width` is documented as the summed display width. The fast path is meant only as an optimisation, but it changes the result for ASCII control characters (`\x00`–`\x1f`, `\x7f`). Line-length decisions can then differ depending on unrelated non-ASCII characters elsewhere in the line. The impact is small because raw control characters rarely appear in source lines.

## Fix

```diff
--- a/src/black/strings.py
+++ b/src/black/strings.py
@@ def str_width(line_str: str) -> int:
-    if line_str.isascii():
+    if line_str.isascii() and line_str.isprintable():
         # Fast path for a line consisting of only ASCII characters
         return len(line_str)
     return sum(map(char_width, line_str))
```

# Bug Report: black.strings.str_width ASCII fast path counts control characters as width 1

**Target**: `black.strings.str_width`
**Severity**: Low
**Bug Type**: Contract
**Date**: 2026-10-05

## Summary

The docstring of `char_width` says "control characters are counted as 0", and `char_width("\x1f") == 0`. But `str_width`'s ASCII fast path returns `len(line_str)`, so `str_width("\x1f") == 1`. As a result `str_width(s) != sum(map(char_width, s))`, and `count_chars_in_width` disagrees with `str_width`.

## Property-Based Test

```python
from hypothesis import given, strategies as st
from black.strings import str_width, char_width

@given(st.text())
def test_width_consistency(s):
    assert str_width(s) == sum(char_width(c) for c in s)
```

**Failing input**: `s='\x1f'`

## Reproducing the Bug

```python
from black.strings import str_width, char_width, count_chars_in_width
assert char_width("\x1f") == 0
assert str_width("\x1f") == 1
assert str_width("a\x1f") != str_width("\u00e9\x1f")  # 2 vs 1
assert count_chars_in_width("\x1f", 0) == 1  # yet str_width of that prefix is 1 > 0
```

## Why This Is A Bug

The same string gets a different width depending on whether it also contains a non-ASCII character, and the two width helpers contradict each other. The practical impact is small because ASCII control characters are rare in source lines.

## Fix

Make the fast path apply only when the string has no ASCII control characters, e.g. `if line_str.isascii() and line_str.isprintable(): return len(line_str)`. Alternatively, make the width table treat ASCII control characters as width 1 so both paths agree.

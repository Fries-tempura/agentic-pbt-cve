# Bug Report: soupsieve.css_parser quadratic-time parsing of selectors with long whitespace runs

**Target**: `soupsieve.css_parser.CSSParser.selector_iter` (`RE_WS_END`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`selector_iter` finds trailing whitespace with `RE_WS_END.search(pattern)` where `RE_WS_END = {WSC}*$`. Because the search is not anchored at the start, the regex engine retries at every position inside a whitespace run and fails at the following non-whitespace character, so the cost is O(n²) in the length of the run. Any selector with a long internal run of whitespace (or comments) takes quadratic time to compile, which makes denial of service possible when selectors come from untrusted input.

## Property-Based Test

```python
@pytest.mark.parametrize('tail', ['b', '!'])
def test_whitespace_linear(tail):
    """CLAIM-5: parse time scales linearly with whitespace length."""
    def t(n):
        s = 'a' + ' ' * n + tail
        st_ = time.perf_counter()
        try:
            cp.CSSParser(s).process_selectors()
        except SelectorSyntaxError:
            pass
        return time.perf_counter() - st_
    small, big = t(2000), t(8000)
    assert big < small * 8
```

**Failing input**: `'a' + ' ' * 8000 + 'b'` took 1.50 s vs 0.096 s for 2000 spaces (×15.6 for ×4 input). The `'!'` tail (an invalid selector) is just as slow, so the time is spent before any validation happens.

## Reproducing the Bug

```python
import time
import soupsieve as sv

for n in (5000, 10000, 20000, 40000):
    t = time.perf_counter()
    sv.compile('a' + ' ' * n + 'b')
    print(n, round(time.perf_counter() - t, 2))
```

## Why This Is A Bug

Tokenising a selector should take time linear in its length. Here 40 kB of spaces costs tens of seconds, and the regex is applied before any syntax check, so even inputs that are going to be rejected pay the full quadratic cost. `RE_WS_END.search` on its own shows the same growth (0.38 s at 4000 chars, 1.61 s at 8000).

## Fix

Don't search for the trailing whitespace. Instead, check whether only whitespace or comments remain at the current index. Each check stops at the first non-whitespace character, and the next token then consumes that same run, so the total work is linear.

```diff
-RE_WS_END = re.compile(fr'{WSC}*$')
+RE_WS_END = re.compile(fr'{WSC}*\Z')
@@ def selector_iter(self, pattern: str) -> Iterator[tuple[str, Match[str]]]:
-        m = RE_WS_END.search(pattern)
-        end = (m.start(0) - 1) if m else (len(pattern) - 1)
 ...
-        while index <= end:
+        while index < len(pattern) and not RE_WS_END.match(pattern, index):
```

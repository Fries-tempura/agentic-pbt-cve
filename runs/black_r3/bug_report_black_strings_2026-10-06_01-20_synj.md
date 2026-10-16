# Bug Report: black.strings.lines_with_leading_tabs_expanded Catastrophic (cubic) regex backtracking

**Target**: `black.strings.lines_with_leading_tabs_expanded` (reached via `fix_docstring` / `black.format_str`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`FIRST_NON_WHITESPACE_RE = r"\s*\t+\s*(\S)"` backtracks catastrophically when a line consists of many tabs/whitespace with no following non-whitespace character. Run time grows roughly cubically with line length. A docstring with a few thousand tabs makes Black hang (ReDoS).

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
from black.strings import lines_with_leading_tabs_expanded

@settings(max_examples=50, deadline=None)
@given(st.integers(100, 1000), st.sampled_from([" \t", "\t", "\t "]))
def test_tabs_expanded_linear_time(n, unit):
    s = unit * n
    t = time.perf_counter()
    lines_with_leading_tabs_expanded(s)
    assert time.perf_counter() - t < 0.1, n
```

**Failing input**: `n=275, unit='\t'`

## Reproducing the Bug

```python
import time, black
from black.strings import lines_with_leading_tabs_expanded

for n in [250, 500, 1000, 2000]:
    t = time.perf_counter()
    lines_with_leading_tabs_expanded("\t" * n)
    print(n, time.perf_counter() - t)
# 250 0.05s, 500 0.42s, 1000 3.3s, 2000 25.7s

src = 'def f():\n    """x\n' + "\t" * 1000 + '"""\n'
black.format_str(src, mode=black.Mode())  # ~3s; grows cubically with tab count
```

## Why This Is A Bug

The function only needs to find the leading-whitespace prefix of each line, which takes linear time. Because `\s*`, `\t+` and `\s*` all overlap on tab characters and the match must fail when no `\S` follows, the regex engine tries O(n²) splits at each of O(n) start positions. Black runs this on every docstring it formats, so untrusted source code (e.g. in CI, pre-commit hooks, or blackd) can make Black hang. This is a denial of service (CVE-2024-21503).

## Fix

```diff
-FIRST_NON_WHITESPACE_RE: Final = re.compile(r"\s*\t+\s*(\S)")
@@ def lines_with_leading_tabs_expanded(s: str) -> List[str]:
     lines = []
     for line in s.splitlines():
-        # Find the index of the first non-whitespace character after a string of
-        # whitespace that includes at least one tab
-        match = FIRST_NON_WHITESPACE_RE.match(line)
-        if match:
-            first_non_whitespace_idx = match.start(1)
-
-            lines.append(
-                line[:first_non_whitespace_idx].expandtabs()
-                + line[first_non_whitespace_idx:]
-            )
-        else:
-            lines.append(line)
+        stripped_line = line.lstrip()
+        if not stripped_line or stripped_line == line:
+            lines.append(line)
+        else:
+            prefix_length = len(line) - len(stripped_line)
+            prefix = line[:prefix_length].expandtabs()
+            lines.append(prefix + stripped_line)
     if s.endswith("\n"):
         lines.append("")
     return lines
```

# Bug Report: black.strings.lines_with_leading_tabs_expanded Polynomial (cubic) backtracking on tab-only lines (ReDoS)

**Target**: `black.strings.lines_with_leading_tabs_expanded` (reached via `fix_docstring` / `black.format_str`)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`FIRST_NON_WHITESPACE_RE = re.compile(r"\s*\t+\s*(\S)")` uses three adjacent overlapping quantifiers. A line made only of whitespace and tabs (with no following non-whitespace character) makes the regex backtrack catastrophically, so the run time is O(n^3) in the line length. The pattern runs on every docstring line that Black formats, so a crafted source file can make Black hang (CVE-2024-21503).

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
from black.strings import lines_with_leading_tabs_expanded

@settings(max_examples=50, deadline=None)
@given(st.integers(1000, 5000), st.sampled_from(["\t", " \t", "\t "]))
def test_tabs_expanded_linear_time(n, unit):
    t = time.perf_counter()
    lines_with_leading_tabs_expanded("\t" * n)
    assert time.perf_counter() - t < 1.0
```

**Failing input**: `n=1000` (a line of 1000 tab characters)

## Reproducing the Bug

```python
import time, black
for n in [250, 500, 1000, 2000]:
    src = 'def f():\n    """x\n' + "\t" * n + '"""\n'
    t = time.perf_counter()
    black.format_str(src, mode=black.Mode())
    print(n, time.perf_counter() - t)
```

Observed: 250 → 0.026s, 500 → 0.19s, 1000 → 1.5s, 2000 → 12.2s (each doubling of n costs about 8×, i.e. cubic). Calling `lines_with_leading_tabs_expanded("\t" * 2000)` directly takes about 12s.

## Why This Is A Bug

The function only needs to expand leading tabs, which is a linear-time job. Instead, ordinary-looking input (a docstring line of tabs) makes the formatter's run time blow up polynomially. Anything that runs Black on untrusted code (CI, editors, blackd) can be stalled this way. This is denial of service via regex backtracking.

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
```

# Bug Report: black.strings.lines_with_leading_tabs_expanded Catastrophic regex backtracking (ReDoS) on tab-only lines

**Target**: `black.strings.lines_with_leading_tabs_expanded` (reached via `black.format_str` → `fix_docstring`)
**Severity**: High
**Bug Type**: Logic (algorithmic complexity / denial of service)
**Date**: 2026-10-06

## Summary

`FIRST_NON_WHITESPACE_RE = r"\s*\t+\s*(\S)"` backtracks catastrophically when a line has many whitespace characters (especially tabs) and no non-whitespace character. Running time grows roughly cubically: 2,000 tabs take about 12.7 s. Any docstring with such a line makes Black hang, so a small crafted file can stall formatters, pre-commit hooks or CI.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
from black.strings import lines_with_leading_tabs_expanded

@settings(max_examples=20, deadline=None)
@given(st.integers(min_value=500, max_value=4000))
def test_tabs_linear_time(n):
    t = time.perf_counter()
    lines_with_leading_tabs_expanded("\t" * n)
    assert time.perf_counter() - t < 0.1
```

**Failing input**: `n=500` (`"\t" * 500` takes ~0.2 s; time grows ~8× each time n doubles)

## Reproducing the Bug

```python
import time, black

for n in (250, 500, 1000):
    src = 'def f():\n    """doc\n' + "\t" * n + '\n    """\n'
    t = time.perf_counter()
    black.format_str(src, mode=black.Mode())
    print(n, round(time.perf_counter() - t, 3))
```

Observed timings:

| input | n=250 | n=500 | n=1000 | n=2000 |
|---|---|---|---|---|
| `lines_with_leading_tabs_expanded("\t"*n)` | 0.026 s | 0.198 s | 1.546 s | 12.7 s |
| `black.format_str` with that line in a docstring | 0.025 s | 0.193 s | 1.649 s | — |

## Why This Is A Bug

This function only needs to expand a line's leading tabs, which is a linear-time job. Because the regex nests `\s*`, `\t+` and `\s*`, a tab-only line with no `\S` forces the regex engine to retry an O(n²) number of splits at each start position. Black processes untrusted source code (for example in CI or editor integrations), so this is a denial-of-service vector (CVE-2024-21503).

## Fix

The replacement below gives the same output as the original on 3,000 Hypothesis-generated inputs and handles 100,000 tabs in under 0.5 s:

```diff
--- a/src/black/strings.py
+++ b/src/black/strings.py
@@
 STRING_PREFIX_RE: Final = re.compile(
     r"^([" + STRING_PREFIX_CHARS + r"]*)(.*)$", re.DOTALL
 )
-FIRST_NON_WHITESPACE_RE: Final = re.compile(r"\s*\t+\s*(\S)")
 UNICODE_ESCAPE_RE: Final = re.compile(
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
+            prefix = line[:prefix_length]
+            if "\t" in prefix:
+                lines.append(prefix.expandtabs() + stripped_line)
+            else:
+                lines.append(line)
     if s.endswith("\n"):
         lines.append("")
     return lines
```

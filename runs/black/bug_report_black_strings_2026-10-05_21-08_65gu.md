# Bug Report: black.strings Catastrophic regex backtracking (ReDoS) in `lines_with_leading_tabs_expanded`

**Target**: `black.strings.lines_with_leading_tabs_expanded` (via `FIRST_NON_WHITESPACE_RE`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`FIRST_NON_WHITESPACE_RE = re.compile(r"\s*\t+\s*(\S)")` has three adjacent overlapping quantifiers. When a line has many tabs or whitespace characters and no non-whitespace character, the regex backtracks in polynomial (about cubic) time. Every docstring black formats goes through `fix_docstring` → `lines_with_leading_tabs_expanded`, so a short, untrusted source file can hang the formatter. This matches CVE-2024-21503.

## Property-Based Test

```python
@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=2000, max_value=4000))
def test_leading_tabs_linear_time(n):
    line = "\t" * n
    start = time.perf_counter()
    lines_with_leading_tabs_expanded("x\n" + line + "\n")
    assert time.perf_counter() - start < 0.5, n
```

**Failing input**: `n=2000` (took about 12 s in a single call)

## Reproducing the Bug

```python
import time
import black
from black.strings import lines_with_leading_tabs_expanded

for n in (250, 500, 1000):
    t = time.perf_counter()
    lines_with_leading_tabs_expanded("\t" * n)
    print(n, time.perf_counter() - t)

src = 'def f():\n    """x\n' + "\t" * 1000 + '\n    """\n'
t = time.perf_counter()
black.format_str(src, mode=black.Mode())
print("format_str", time.perf_counter() - t)
```

Observed output: `250 0.026`, `500 0.195`, `1000 1.533`, `format_str 1.54`. Each doubling of the input makes it about 8× slower. At 2000 tabs it takes about 12 s, and the time keeps growing cubically with the input.

## Why This Is A Bug

The function's job is a simple linear scan that expands leading tabs on each line. When there is no `\S` to match, the regex engine tries every way of splitting the whitespace run among `\s*`, `\t+` and `\s*`, at every starting position. That turns a linear task into a polynomial-time one. Black is often run on untrusted code (CI, pre-commit, editor integrations, online formatters), so one small file with a long whitespace-only line in a docstring is enough for a denial of service.

## Fix

```diff
--- a/src/black/strings.py
+++ b/src/black/strings.py
@@
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
+        stripped_line = line.lstrip()
+        if not stripped_line or stripped_line == line:
             lines.append(line)
+        else:
+            prefix_length = len(line) - len(stripped_line)
+            prefix = line[:prefix_length].expandtabs()
+            lines.append(prefix + stripped_line)
     if s.endswith("\n"):
         lines.append("")
     return lines
```

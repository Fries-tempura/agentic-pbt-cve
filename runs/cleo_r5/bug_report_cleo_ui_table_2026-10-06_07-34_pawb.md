# Bug Report: cleo.ui.table catastrophic regex backtracking (ReDoS) in _render_cell

**Target**: `cleo.ui.table.Table._render_cell`
**Severity**: Medium
**Bug Type**: Logic (ReDoS / super-linear runtime)
**Date**: 2026-10-06

## Summary

The regex used in `_render_cell` to detect whether a styled cell is "styled by tag" is vulnerable to catastrophic backtracking. Rendering a styled `TableCell` whose content contains a run of `word=word` segments causes exponential-time matching: render time roughly quadruples per added segment (3.8s at 24 segments), so a modest cell value hangs the process.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell
from cleo.ui.table_cell_style import TableCellStyle

@settings(max_examples=20, deadline=None)
@given(st.integers(10, 30))
def test_styled_cell_render_time(n):
    cell = TableCell("<a=" + "aaa=" * n + "!", style=TableCellStyle(cell_format="{}"))
    start = time.time()
    Table(BufferedIO()).set_rows([[cell]]) and None
    t = Table(BufferedIO())
    t.set_rows([[cell]])
    t.render()
    assert time.time() - start < 1.0
```

**Failing input**: `n=22` and above (payload `"<a=" + "aaa="*22 + "!"`)

## Reproducing the Bug

```python
import time
from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell
from cleo.ui.table_cell_style import TableCellStyle

for n in (14, 18, 22, 24):
    t = Table(BufferedIO())
    t.set_rows([[TableCell("<a=" + "aaa=" * n + "!", style=TableCellStyle(cell_format="{}"))]])
    start = time.time()
    t.render()
    print(n, round(time.time() - start, 3))
```

Output (approx):
```
14 0.004
18 0.059
22 1.015
24 3.817
```

## Why This Is A Bug

`_render_cell` (table.py:378-380) tests each styled cell against:

```python
re.match(r"^<(\w+|(\w+=[\w,]+;?)*)>.+</(\w+|(\w+=\w+;?)*)?>$", str(cell))
```

The subpattern `(\w+=[\w,]+;?)*` is a classic nested-quantifier form: for an input like `<a=aaa=aaa=...` that starts to match but ultimately fails (no closing `>` in the expected place), the engine explores exponentially many ways to partition the `\w+=[\w,]+` segments, giving `O(2^n)` runtime. Cell contents are arbitrary user/application data, so a cell value of only a few dozen characters can freeze rendering — a denial-of-service in any program that renders externally-supplied strings in styled table cells.

## Fix

Make the alternation unambiguous and non-backtracking. Anchoring the inner group and removing the overlap between `\w+` and `\w+=...` (e.g. require the separator or use a possessive/atomic form) eliminates the exponential blowup. A minimal change that removes the nested-quantifier ambiguity:

```diff
--- a/src/cleo/ui/table.py
+++ b/src/cleo/ui/table.py
@@ def _render_cell
-            is_not_styled_by_tag = not re.match(
-                r"^<(\w+|(\w+=[\w,]+;?)*)>.+</(\w+|(\w+=\w+;?)*)?>$", str(cell)
-            )
+            is_not_styled_by_tag = not re.match(
+                r"^<(?:\w+|(?:\w+=[\w,]+;?)++)>.+</(?:\w+|(?:\w+=\w+;?)*)?>$",
+                str(cell),
+            )
```

(The `++` possessive quantifier prevents backtracking into the inner group; equivalently, the tag-detection could be reimplemented without a regex.)

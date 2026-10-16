# Bug Report: cleo.ui.table Rendering any TableCell with a default TableCellStyle crashes with IndexError

**Target**: `cleo.ui.table.Table._render_cell` / `cleo.ui.table_cell_style.TableCellStyle.tag`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-05

## Summary

If a `TableCell` has a `TableCellStyle` without an explicit `cell_format`, and its text is not already wrapped in style tags, `Table.render()` crashes. The cause is that `TableCellStyle.tag` returns the unfilled template `"<fg={};bg={}>"`. `_render_cell` then builds the format string `"<<fg={};bg={}>>{}</>"`, which has three `{}` placeholders but receives only one argument.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell
from cleo.ui.table_cell_style import TableCellStyle

tokens = st.sampled_from(["a", "b", "=", ",", ";", "<", ">", "</", "1", "_"])


@settings(max_examples=100, deadline=None)
@given(st.lists(tokens, min_size=1, max_size=8), st.integers(1, 40), st.sampled_from(["", "!", ">", "<"]))
def test_styled_cell_render_is_fast(unit, n, suffix):
    content = "<" + "".join(unit) * n + suffix
    cell = TableCell(content, style=TableCellStyle(fg="red"))
    io = BufferedIO()
    table = Table(io)
    table.set_headers(["h"])
    table.set_rows([[cell]])
    start = time.perf_counter()
    table.render()
    assert time.perf_counter() - start < 1.0
```

**Failing input**: `unit=['a'], n=1, suffix=''` (it fails for every generated value)

## Reproducing the Bug

```python
from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell
from cleo.ui.table_cell_style import TableCellStyle

table = Table(BufferedIO())
table.set_rows([[TableCell("hello", style=TableCellStyle(fg="red"))]])
table.render()
```

```
IndexError: Replacement index 1 out of range for positional args tuple
```

## Why This Is A Bug

`TableCellStyle(fg=..., bg=..., options=...)` is the public way to style a table cell, and `_render_cell` has a code path written specifically for it. That path crashes every time. The `tag` property never puts `self._fg` and `self._bg` into its template, and `_render_cell` wraps the result in a second pair of angle brackets. A related issue in `TableCellStyle` is that `align` is ignored (`self._align = "left"` is hardcoded), and `"left"` uses `rjust`, so text actually ends up right-aligned.

## Fix

```diff
--- a/src/cleo/ui/table_cell_style.py
+++ b/src/cleo/ui/table_cell_style.py
@@
-        self._align = "left"
+        self._align = align
@@
     def tag(self) -> str:
-        tag = "<fg={};bg={}"
+        tag = f"fg={self._fg};bg={self._bg}"
 
         if self._options:
             tag += f';options={",".join(self._options)}'
 
-        tag += ">"
-
         return tag
 
     def pad(self, string: str, length: int, char: str = " ") -> str:
         if self._align == "left":
-            return string.rjust(length, char)
+            return string.ljust(length, char)
 
         if self._align == "right":
-            return string.ljust(length, char)
+            return string.rjust(length, char)
```

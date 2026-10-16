# Bug Report: cleo.ui.table TableCell with TableCellStyle crashes render() with IndexError

**Target**: `cleo.ui.table.Table.render`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-06

## Summary

Rendering a table containing any `TableCell` that carries a `TableCellStyle` (and no explicit `cell_format`) raises `IndexError: Replacement index 1 out of range for positional args tuple`, making per-cell styling unusable.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell
from cleo.ui.table_cell_style import TableCellStyle

plain = st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"),
                                       max_codepoint=127), max_size=10)

@settings(max_examples=100)
@given(plain.filter(bool), st.sampled_from(["left", "right"]))
def test_styled_cell_renders(text, align):
    io = BufferedIO()
    t = Table(io)
    t.set_rows([[TableCell(text, style=TableCellStyle(align=align))]])
    t.render()
```

**Failing input**: `text='0', align='left'` (any non-empty text)

## Reproducing the Bug

```python
from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell
from cleo.ui.table_cell_style import TableCellStyle

t = Table(BufferedIO())
t.set_rows([[TableCell("x", style=TableCellStyle())]])
t.render()
```

## Why This Is A Bug

`TableCellStyle.tag` returns the literal string `"<fg={};bg={}>"` — the `{}` placeholders are never filled. In `Table._render_cell` (table.py:384-386), when a cell has a style but no `cell_format`, the code builds:

```python
cell_format = f"<{cell.style.tag}>{{}}</>"   # -> "<<fg={};bg={}>>{}</>"
```

and later calls `cell_format.format(...)` (table.py:398). That string now contains three `{}` fields, but `.format()` is given a single argument, so Python raises `IndexError`. Attaching a `TableCellStyle` to a cell is a documented, intended feature (it drives the `fg`/`bg`/`align` rendering path), yet it crashes for every ordinary input.

## Fix

The `tag` property should emit a concrete tag using the configured foreground/background colors instead of leaving `{}` placeholders:

```diff
--- a/src/cleo/ui/table_cell_style.py
+++ b/src/cleo/ui/table_cell_style.py
@@ def tag(self) -> str:
-        tag = "<fg={};bg={}"
+        tag = f"<fg={self._fg};bg={self._bg}"

         if self._options:
             tag += f';options={",".join(self._options)}'

         tag += ">"

         return tag
```

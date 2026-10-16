# Bug Report: cleo.ui.table `set_column_max_width` sets the minimum width instead of the maximum

**Target**: `cleo.ui.table.Table.set_column_max_width`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`Table.set_column_max_width(column_index, width)` writes to `self._column_widths` (used as a *minimum* width) instead of `self._column_max_widths`. So a max width never limits a column. Instead it acts like `set_column_width` and can make a column wider. The code that wraps cells to a max width (`_build_table_rows`, `_get_cell_width`) can never run.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table


def render(headers, rows, style="default", **kw):
    io = BufferedIO()
    t = Table(io, style=style)
    if headers:
        t.set_headers(headers)
    t.set_rows(rows)
    for k, v in kw.items():
        getattr(t, k)(*v)
    t.render()
    return io.fetch_output().splitlines()


@settings(max_examples=300)
@given(st.text(st.characters(min_codepoint=97, max_codepoint=122), min_size=10, max_size=40),
       st.integers(1, 8))
def test_column_max_width(text, w):
    lines = render(["h"], [[text]], set_column_max_width=(0, w))
    # default style: "| " + content + " |"
    assert max(len(l) for l in lines) <= w + 4, lines
```

**Failing input**: `text='aaaaaaaaaa', w=1`

## Reproducing the Bug

```python
from cleo.io.outputs.buffered_output import BufferedOutput
from cleo.ui.table import Table

o = BufferedOutput()
t = Table(o)
t.set_headers(["h"])
t.set_rows([["aaaaaaaaaa"]])
t.set_column_max_width(0, 3)
t.render()
print(o.fetch())
print(t._column_max_widths)

o = BufferedOutput()
t = Table(o)
t.set_headers(["h"])
t.set_rows([["a"]])
t.set_column_max_width(0, 10)
t.render()
print(o.fetch())
```

Output:

```
+------------+
| h          |
+------------+
| aaaaaaaaaa |
+------------+

{}
+------------+
| h          |
+------------+
| a          |
+------------+
```

In the first table the column is not limited to 3 characters. In the second, the "max width" of 10 pads the column out to 10.

## Why This Is A Bug

The method is named `set_column_max_width`, and the table has a separate `_column_max_widths` dict. `_build_table_rows` reads that dict to wrap long cells with `formatter.format_and_wrap`, and `_get_cell_width` reads it to cap column widths. This port follows Symfony's `Table::setColumnMaxWidth`, which sets the maximum width and wraps the content. Here nothing ever writes to `_column_max_widths`, so that code is dead. The method behaves exactly like `set_column_width`, which sets a minimum. A user who asks for a cap of N gets a column at least N wide.

If you populate `_column_max_widths` directly, wrapping works when the table was built with an `Output` (`| aaa | aaa | aaa | a |` on separate lines). When the table was built with an `IO` (e.g. `BufferedIO`), it fails at `assert isinstance(self._io, Output)` in `_build_table_rows`. So once the setter is fixed, the formatter lookup also has to handle `IO`.

## Fix

```diff
--- a/src/cleo/ui/table.py
+++ b/src/cleo/ui/table.py
@@ def set_column_max_width(self, column_index: int, width: int) -> Table:
-        self._column_widths[column_index] = width
+        self._column_max_widths[column_index] = width
 
         return self
@@ def _build_table_rows(self, rows: Rows) -> Iterator[Row | TableSeparator]:
                 ] < len(self._io.remove_format(cell)):
-                    assert isinstance(self._io, Output)
-                    cell = self._io.formatter.format_and_wrap(
+                    output = (
+                        self._io if isinstance(self._io, Output) else self._io.output
+                    )
+                    cell = output.formatter.format_and_wrap(
                         cell, self._column_max_widths[column] * colspan
                     )
```

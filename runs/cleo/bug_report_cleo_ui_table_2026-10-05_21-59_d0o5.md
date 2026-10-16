# Bug Report: cleo.ui.table set_column_max_width sets a minimum width instead of a maximum

**Target**: `cleo.ui.table.Table.set_column_max_width`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`Table.set_column_max_width(i, w)` writes to `self._column_widths` (the minimum width) instead of `self._column_max_widths`. As a result, the max width is never applied: long cells are not wrapped or limited, and short columns are padded out to `w`.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table

plain = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters="<>\\"),
    max_size=20,
)


@st.composite
def table_data(draw):
    ncols = draw(st.integers(1, 5))
    headers = draw(st.lists(plain, min_size=ncols, max_size=ncols))
    rows = draw(st.lists(st.lists(plain, min_size=ncols, max_size=ncols), max_size=6))
    return headers, rows


@settings(max_examples=200)
@given(table_data(), st.integers(1, 10))
def test_column_max_width_limits_column(data, max_width):
    headers, rows = data
    io = BufferedIO()
    table = Table(io)
    table.set_headers(headers)
    table.set_rows(rows)
    table.set_column_max_width(0, max_width)
    table.render()
    out = io.fetch_output()
    col0 = out.splitlines()[0].split("+")[1]
    assert len(col0) <= max_width + 2, out
```

**Failing input**: `data=(['00'], []), max_width=1`

## Reproducing the Bug

```python
from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table

io = BufferedIO()
table = Table(io)
table.set_rows([["a very long cell value"], ["x"]])
table.set_column_max_width(0, 5)
table.render()
print(io.fetch_output())

io = BufferedIO()
table = Table(io)
table.set_rows([["x"]])
table.set_column_max_width(0, 5)
table.render()
assert io.fetch_output().splitlines()[0] == "+---+", io.fetch_output()
```

## Why This Is A Bug

The method name and the `_column_max_widths` dict, which `_build_table_rows` and `_get_cell_width` both read, show that it should set a maximum. Instead it behaves exactly like `set_column_width`, which sets a minimum. Because nothing ever writes to `_column_max_widths`, the wrapping code in `_build_table_rows` can never run.

## Fix

```diff
     def set_column_max_width(self, column_index: int, width: int) -> Table:
-        self._column_widths[column_index] = width
+        self._column_max_widths[column_index] = width
 
         return self
```

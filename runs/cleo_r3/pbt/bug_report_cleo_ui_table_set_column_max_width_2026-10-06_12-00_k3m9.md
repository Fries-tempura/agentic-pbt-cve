# Bug Report: cleo.ui.table Table.set_column_max_width has no effect

**Target**: `cleo.ui.table.Table.set_column_max_width`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`Table.set_column_max_width()` writes into `_column_widths` (the *minimum* width dict) instead of `_column_max_widths`. As a result the max width is never applied (cells are never wrapped), and the value is instead treated as a minimum column width.

## Property-Based Test

```python
@settings(max_examples=200)
@given(st.lists(st.lists(text, min_size=1, max_size=3), min_size=1, max_size=4), st.integers(1, 5))
def test_max_width(rows, w):
    out = BufferedOutput()
    t = Table(out)
    t.set_rows(rows).set_column_max_width(0, w)
    t.render()
    lines = out.fetch().splitlines()
    first = lines[0].split("+")[1]
    assert len(first) <= w + 2, lines
```

**Failing input**: `rows=[['00']], w=1`

## Reproducing the Bug

```python
from cleo.io.outputs.buffered_output import BufferedOutput
from cleo.ui.table import Table

o = BufferedOutput()
t = Table(o)
t.set_rows([["abcdefghij", "x"]]).set_column_max_width(0, 3)
t.render()
print(o.fetch())
assert t._column_max_widths == {}
```

Output:
```
+------------+---+
| abcdefghij | x |
+------------+---+
```
Expected (what the wrapping code produces when `_column_max_widths[0] = 3`):
```
+-----+---+
| abc | x |
| def |   |
| ghi |   |
| j   |   |
+-----+---+
```

## Why This Is A Bug

`_build_table_rows` and `_get_cell_width` read `_column_max_widths` to wrap and cap columns, but nothing ever writes to it. The setter is a copy-paste of `set_column_width`, so the public API does nothing it says and quietly sets a minimum width instead.

## Fix

```diff
     def set_column_max_width(self, column_index: int, width: int) -> Table:
-        self._column_widths[column_index] = width
+        self._column_max_widths[column_index] = width
 
         return self
```

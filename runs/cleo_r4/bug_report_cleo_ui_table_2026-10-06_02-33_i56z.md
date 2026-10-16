# Bug Report: cleo.ui.table Table.set_column_max_width has no effect

**Target**: `cleo.ui.table.Table.set_column_max_width`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`Table.set_column_max_width` stores the width in `_column_widths` (the minimum width) instead of `_column_max_widths`. As a result, the maximum width is never applied, content is never wrapped, and the call actually forces a *minimum* width.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from cleo.io.outputs.buffered_output import BufferedOutput
from cleo.ui.table import Table

@settings(max_examples=100)
@given(st.lists(st.text(alphabet="abcdef", min_size=1, max_size=40), min_size=1, max_size=4),
       st.integers(1, 10))
def test_set_column_max_width(cells, w):
    out = BufferedOutput()
    t = Table(out)
    t.set_rows([cells])
    t.set_column_max_width(0, w)
    t.render()
    lines = out.fetch().splitlines()
    first = lines[1].split("|")[1]
    assert len(first) <= w + 2, (cells, w, lines)
```

**Failing input**: `cells=['aa'], w=1`

## Reproducing the Bug

```python
from cleo.io.outputs.buffered_output import BufferedOutput
from cleo.ui.table import Table

out = BufferedOutput()
t = Table(out)
t.set_rows([["abcdefgh", "x"]])
t.set_column_max_width(0, 3)
t.render()
print(out.fetch())
assert t._column_max_widths == {}
```

Output: `| abcdefgh | x |`, not wrapped.

## Why This Is A Bug

The method is named and meant to set a maximum column width (mirroring Symfony's `Table::setColumnMaxWidth`). `Table` already has a `_column_max_widths` dict, and `_build_table_rows` / `_get_cell_width` use it to wrap and cap cells, but nothing ever writes to it. The method is a copy-paste of `set_column_width`, so it silently does the wrong thing: it sets a minimum, and a small "max" value can never shrink a column. When `_column_max_widths` is populated directly, wrapping works (`abc / def / gh`), which confirms the intended behavior.

## Fix

```diff
     def set_column_max_width(self, column_index: int, width: int) -> Table:
-        self._column_widths[column_index] = width
+        self._column_max_widths[column_index] = width

         return self
```

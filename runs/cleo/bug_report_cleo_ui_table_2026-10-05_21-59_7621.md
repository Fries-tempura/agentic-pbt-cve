# Bug Report: cleo.ui.table Exponential-time regex (ReDoS) when rendering styled cells

**Target**: `cleo.ui.table.Table._render_cell`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`Table._render_cell` checks every `TableCell` that has a `TableCellStyle` against the regex `^<(\w+|(\w+=[\w,]+;?)*)>.+</(\w+|(\w+=\w+;?)*)?>$`. The nested quantifier `(\w+=[\w,]+;?)*` backtracks catastrophically. A cell value of only 73 characters takes more than 1 second to render, and each extra 7 characters makes it about 5× slower. This is a ReDoS: a CLI that puts untrusted text (file names, API data) into a styled table can be made to hang.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st
from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell
from cleo.ui.table_cell_style import TableCellStyle


def render(headers, rows):
    io = BufferedIO()
    table = Table(io)
    table.set_headers(headers)
    table.set_rows(rows)
    table.render()
    return io.fetch_output()


@settings(max_examples=50, deadline=None)
@given(st.integers(2, 6), st.integers(5, 25), st.sampled_from(["", "!", "<"]))
def test_styled_cell_key_value_render_is_fast(seg_len, n, suffix):
    content = "<a=" + ("b" * seg_len + "=") * n + suffix
    cell = TableCell(content, style=TableCellStyle(fg="red", cell_format="{}"))
    start = time.perf_counter()
    render(["h"], [[cell]])
    assert time.perf_counter() - start < 1.0, (len(content), repr(content))
```

**Failing input**: `seg_len=6, n=10, suffix=''`, i.e. `content = "<a=" + "bbbbbb=" * 10` (73 chars)

## Reproducing the Bug

```python
import time
from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell
from cleo.ui.table_cell_style import TableCellStyle

for n in range(6, 12):
    table = Table(BufferedIO())
    table.set_rows([[TableCell("<a=" + "bbbbbb=" * n, style=TableCellStyle(cell_format="{}"))]])
    t = time.perf_counter()
    table.render()
    print(n, round(time.perf_counter() - t, 3))
```

Measured time for the regex alone: n=6: 0.002s, n=7: 0.012s, n=8: 0.057s, n=9: 0.248s, n=10: 1.335s. That is about 5× more per segment.

## Why This Is A Bug

Rendering a table should take time roughly linear in the size of its contents. Here, a short and ordinary-looking string causes exponential backtracking, so any program that renders untrusted data in a styled cell can be made to hang (denial of service). This is the issue tracked as CVE-2022-42966.

## Fix

Make the repetition unambiguous so a key/value boundary can only be split one way. For example, values must not contain `=`, and pairs must be separated by `;`:

```diff
-            is_not_styled_by_tag = not re.match(
-                r"^<(\w+|(\w+=[\w,]+;?)*)>.+</(\w+|(\w+=\w+;?)*)?>$", str(cell)
-            )
+            is_not_styled_by_tag = not re.match(
+                r"^<(\w+|(\w+=[\w,]+)(;\w+=[\w,]+)*;?)>.+</(\w+|(\w+=\w+)(;\w+=\w+)*;?)?>$",
+                str(cell),
+            )
```

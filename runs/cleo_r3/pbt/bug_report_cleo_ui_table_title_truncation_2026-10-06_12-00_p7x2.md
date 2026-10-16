# Bug Report: cleo.ui.table Header/footer title breaks border on narrow tables

**Target**: `cleo.ui.table.Table._render_row_separator`
**Severity**: Low
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

If a header or footer title is too long for the table, it is meant to be cut down to fit the border. On narrow tables (border shorter than 9 characters) the length calculation goes negative. The title then makes the border line wider than the table rows, which breaks the table layout.

## Property-Based Test

```python
@settings(max_examples=300)
@given(st.lists(text, min_size=1, max_size=3), st.lists(st.lists(text, min_size=1, max_size=3), max_size=4), text)
def test_title_equal_width(headers, rows, title):
    out = BufferedOutput()
    t = Table(out)
    t.set_headers(headers).set_rows(rows).set_header_title(title).set_footer_title(title)
    t.render()
    lines = out.fetch().splitlines()
    assert len({len(l) for l in lines}) == 1, lines
```

**Failing input**: `headers=[''], rows=[], title=''`

## Reproducing the Bug

```python
from cleo.io.outputs.buffered_output import BufferedOutput
from cleo.ui.table import Table

o = BufferedOutput()
t = Table(o)
t.set_headers(["ISBN"]).set_rows([["x"]]).set_header_title("Books")
t.render()
print(o.fetch())
```

Output:
```
+- Book... -+
| ISBN |
+------+
| x    |
+------+
```

## Why This Is A Bug

The truncation branch is supposed to make the title exactly `limit = markup_length - 4` characters wide. It slices `title[: limit - format_length - 3]`. When `limit - format_length - 3 < 0`, Python's negative slice removes characters from the end of the title rather than giving an empty string. The resulting title is wider than `limit`, and the splice `markup[title_start + title_length:]` assumes it is exactly `limit`, so the top/bottom border gets longer than the rest of the table.

## Fix

Clamp the slice length, and skip the title when it can't fit at all:

```diff
             if title_length > limit:
                 title_length = limit
                 format_length = len(self._io.remove_format(title_format.format("")))
+                keep = limit - format_length - 3
+                if keep < 0:
+                    self._io.write_line(self.style.border_format.format(markup))
+                    return
                 formatted_title = title_format.format(
-                    title[: limit - format_length - 3] + "..."
+                    title[:keep] + "..."
                 )
```

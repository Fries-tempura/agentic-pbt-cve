import time

from hypothesis import given, settings, strategies as st

from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell
from cleo.ui.table_cell_style import TableCellStyle

# Plain ASCII text without formatter tags, backslashes or newlines
plain = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters="<>\\"),
    max_size=20,
)


def render(headers, rows, style="default", configure=None):
    io = BufferedIO()
    table = Table(io, style)
    table.set_headers(headers)
    table.set_rows(rows)
    if configure:
        configure(table)
    table.render()
    return io.fetch_output()


@st.composite
def table_data(draw):
    ncols = draw(st.integers(1, 5))
    headers = draw(st.lists(plain, min_size=ncols, max_size=ncols))
    rows = draw(st.lists(st.lists(plain, min_size=ncols, max_size=ncols), max_size=6))
    return headers, rows


@settings(max_examples=300)
@given(table_data(), st.sampled_from(["default", "borderless", "box", "box-double"]))
def test_all_lines_same_width(data, style):
    headers, rows = data
    out = render(headers, rows, style)
    lines = out.splitlines()
    assert len({len(l) for l in lines}) == 1, out


@settings(max_examples=200)
@given(table_data(), st.integers(1, 10))
def test_column_max_width_limits_column(data, max_width):
    headers, rows = data
    out = render(headers, rows, configure=lambda t: t.set_column_max_width(0, max_width))
    first_border = out.splitlines()[0]
    # first column width = cell content width + 2 padding
    col0 = first_border.split("+")[1]
    assert len(col0) <= max_width + 2, out


@settings(max_examples=200)
@given(table_data())
def test_content_preserved(data):
    headers, rows = data
    out = render(headers, rows)
    for cell in [c for r in [headers] + rows for c in r]:
        assert cell.strip() in out


# Styled cell rendering should be fast regardless of content
tokens = st.sampled_from(["a", "b", "=", ",", ";", "<", ">", "</", "1", "_"])


@settings(max_examples=100, deadline=None)
@given(st.lists(tokens, min_size=1, max_size=8), st.integers(1, 40), st.sampled_from(["", "!", ">", "<"]))
def test_styled_cell_render_is_fast(unit, n, suffix):
    content = "<" + "".join(unit) * n + suffix
    cell = TableCell(content, style=TableCellStyle(fg="red", cell_format="{}"))
    start = time.perf_counter()
    render(["h"], [[cell]])
    assert time.perf_counter() - start < 1.0, repr(content)


@settings(max_examples=50, deadline=None)
@given(st.integers(2, 6), st.integers(5, 25), st.sampled_from(["", "!", "<"]))
def test_styled_cell_key_value_render_is_fast(seg_len, n, suffix):
    content = "<a=" + ("b" * seg_len + "=") * n + suffix
    cell = TableCell(content, style=TableCellStyle(fg="red", cell_format="{}"))
    start = time.perf_counter()
    render(["h"], [[cell]])
    assert time.perf_counter() - start < 1.0, (len(content), repr(content))

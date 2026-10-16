import time
from hypothesis import given, settings, strategies as st, HealthCheck
from cleo.io.buffered_io import BufferedIO
from cleo.io.outputs.output import Verbosity
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell
from cleo.ui.table_cell_style import TableCellStyle

plain = st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), max_codepoint=127), max_size=10)
styles = st.sampled_from(["default", "borderless", "box", "box-double"])

def render(table_setup, style="default"):
    io = BufferedIO()
    t = Table(io, style)
    table_setup(t)
    t.render()
    return io.fetch_output()

@settings(max_examples=300)
@given(st.lists(plain, min_size=1, max_size=4), st.lists(st.lists(plain, max_size=5), max_size=5), styles)
def test_rectangular(headers, rows, style):
    def setup(t):
        t.set_headers(headers)
        t.set_rows(rows)
    out = render(setup, style)
    lines = out.rstrip("\n").split("\n")
    assert len({len(l) for l in lines}) == 1, out

@settings(max_examples=100)
@given(st.lists(st.lists(st.text(alphabet="abc xyz", min_size=1, max_size=40), min_size=1, max_size=3), min_size=1, max_size=4),
       st.integers(1, 10))
def test_max_width(rows, w):
    def setup(t):
        t.set_rows(rows)
        t.set_column_max_width(0, w)
    out = render(setup)
    first = out.split("\n")[0]
    # +-----+  column 0 effective width = content + 2 padding
    col0 = first.split("+")[1]
    assert len(col0) <= w + 2, out

@settings(max_examples=100)
@given(plain.filter(bool), st.sampled_from(["left", "right"]))
def test_styled_cell_renders(text, align):
    def setup(t):
        t.set_rows([[TableCell(text, style=TableCellStyle(align=align))]])
    render(setup)

@settings(max_examples=20, deadline=None)
@given(st.integers(10, 30))
def test_styled_cell_time(n):
    cell = TableCell("<" + "a=a," * n + "\x00>a</>", style=TableCellStyle(cell_format="{}"))
    start = time.time()
    render(lambda t: t.set_rows([[cell]]))
    assert time.time() - start < 1.0

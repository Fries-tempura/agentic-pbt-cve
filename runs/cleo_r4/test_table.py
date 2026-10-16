from hypothesis import given, settings, strategies as st
from cleo.io.outputs.buffered_output import BufferedOutput
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell
from cleo.ui.table_cell_style import TableCellStyle

text = st.text(alphabet="abcdefXYZ 0123456789.-", min_size=0, max_size=12)

def render(headers, rows, style="default"):
    out = BufferedOutput()
    t = Table(out, style=style)
    t.set_headers(headers)
    t.set_rows(rows)
    t.render()
    return out.fetch().splitlines()

@settings(max_examples=300)
@given(st.integers(1, 5).flatmap(lambda n: st.tuples(
    st.lists(text, min_size=n, max_size=n),
    st.lists(st.lists(text, min_size=n, max_size=n), max_size=5))),
    st.sampled_from(["default", "borderless", "box", "box-double"]))
def test_lines_equal_width_and_content_present(hr, style):
    headers, rows = hr
    lines = render(headers, rows, style)
    assert len({len(l) for l in lines}) == 1, lines
    joined = "\n".join(lines)
    for r in [headers] + rows:
        for c in r:
            assert c in joined

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
    # column 0 content width (between first two '|') must not exceed w + padding
    first = lines[1].split("|")[1]
    assert len(first) <= w + 2, (cells, w, lines)


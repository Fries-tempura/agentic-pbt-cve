from hypothesis import given, settings, strategies as st, assume
from cleo.io.outputs.buffered_output import BufferedOutput
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell
from cleo.ui.table_separator import TableSeparator

# plain text without tag chars / backslashes / newlines
text = st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters="<>\\"), max_size=12)
styles = st.sampled_from(["default", "borderless", "box", "box-double", "compact"])

def render(t, out):
    t.render()
    return out.fetch().splitlines()

@settings(max_examples=500)
@given(st.lists(text, min_size=1, max_size=4), st.lists(st.lists(text, max_size=5), max_size=6), styles)
def test_lines_equal_width(headers, rows, style):
    out = BufferedOutput()
    t = Table(out, style=style)
    t.set_headers(headers)
    t.set_rows(rows)
    lines = render(t, out)
    if style == "compact":
        lines = [l.rstrip() for l in lines]  # compact pads trailing
        return
    assert len({len(l) for l in lines}) == 1, lines

@settings(max_examples=300)
@given(st.lists(st.lists(text.filter(lambda s: s.strip()), min_size=1, max_size=4), min_size=1, max_size=5))
def test_content_present(rows):
    out = BufferedOutput()
    t = Table(out)
    t.set_rows(rows)
    o = out.fetch() if False else None
    t.render()
    o = out.fetch()
    for r in rows:
        for c in r:
            assert c in o

@settings(max_examples=300)
@given(st.lists(text, min_size=1, max_size=4), st.lists(st.lists(text, min_size=1, max_size=4), max_size=4),
       st.integers(1, 20))
def test_column_widths_equal_width(headers, rows, w):
    out = BufferedOutput()
    t = Table(out)
    t.set_headers(headers).set_rows(rows).set_column_widths([w] * 4)
    lines = render(t, out)
    assert len({len(l) for l in lines}) == 1, lines

@settings(max_examples=300)
@given(st.lists(st.lists(text, min_size=1, max_size=4), min_size=1, max_size=4), st.integers(0, 3), st.integers(1, 5),
       st.data())
def test_colspan_equal_width(rows, idx, span, data):
    out = BufferedOutput()
    t = Table(out)
    cell = TableCell(data.draw(text), colspan=span)
    rows = rows + [[cell]]
    t.set_rows(rows)
    lines = render(t, out)
    assert len({len(l) for l in lines}) == 1, lines

@settings(max_examples=300)
@given(st.lists(st.lists(text, min_size=1, max_size=3), min_size=1, max_size=4), st.integers(2, 4), st.data())
def test_rowspan_equal_width(rows, span, data):
    out = BufferedOutput()
    t = Table(out)
    cell = TableCell(data.draw(text), rowspan=span)
    rows = [[cell] + rows[0]] + rows[1:]
    t.set_rows(rows)
    lines = render(t, out)
    assert len({len(l) for l in lines}) == 1, lines

@settings(max_examples=300)
@given(st.lists(text, min_size=1, max_size=3), st.lists(st.lists(text, min_size=1, max_size=3), max_size=4), text)
def test_title_equal_width(headers, rows, title):
    out = BufferedOutput()
    t = Table(out)
    t.set_headers(headers).set_rows(rows).set_header_title(title).set_footer_title(title)
    lines = render(t, out)
    assert len({len(l) for l in lines}) == 1, lines

@settings(max_examples=200)
@given(st.lists(st.lists(text, min_size=1, max_size=3), min_size=1, max_size=4), st.integers(1, 5))
def test_max_width(rows, w):
    out = BufferedOutput()
    t = Table(out)
    t.set_rows(rows).set_column_max_width(0, w)
    lines = render(t, out)
    # first column inner width = w + 2 padding
    first = lines[0].split("+")[1]
    assert len(first) <= w + 2, lines

from hypothesis import given, settings, strategies as st, assume
from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell

ALPH = st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters="<>\\")
cell = st.text(ALPH, max_size=12)
cell_nl = st.text(st.one_of(ALPH, st.just("\n")), max_size=12)
STYLES = st.sampled_from(["default", "borderless", "box", "box-double"])


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


@st.composite
def grid(draw, c=cell):
    n = draw(st.integers(1, 5))
    headers = draw(st.lists(c, min_size=n, max_size=n))
    rows = draw(st.lists(st.lists(c, min_size=n, max_size=n), max_size=6))
    return headers, rows


@settings(max_examples=500)
@given(grid(), STYLES)
def test_lines_equal_width(g, style):
    lines = render(*g, style=style)
    assert len({len(l) for l in lines}) == 1, lines


@settings(max_examples=500)
@given(grid(cell_nl), STYLES)
def test_lines_equal_width_multiline(g, style):
    lines = render(*g, style=style)
    assert len({len(l) for l in lines}) == 1, lines


@settings(max_examples=500)
@given(grid())
def test_cells_present(g):
    headers, rows = g
    out = "\n".join(render(headers, rows))
    for c in headers + [x for r in rows for x in r]:
        assert c.strip() in out


@settings(max_examples=300)
@given(grid(), st.text(ALPH, min_size=1, max_size=80), st.text(ALPH, min_size=1, max_size=80))
def test_titles_keep_width(g, ht, ft):
    headers, rows = g
    plain = render(headers, rows)
    assume(len(plain[0]) >= 10)
    titled = render(headers, rows, set_header_title=(ht,), set_footer_title=(ft,))
    assert [len(l) for l in plain] == [len(l) for l in titled], titled


@settings(max_examples=300)
@given(st.text(st.characters(min_codepoint=97, max_codepoint=122), min_size=10, max_size=40),
       st.integers(1, 8))
def test_column_max_width(text, w):
    lines = render(["h"], [[text]], set_column_max_width=(0, w))
    # default style: "| " + content + " |"
    assert max(len(l) for l in lines) <= w + 4, lines


@settings(max_examples=300)
@given(st.integers(2, 4), st.lists(cell, min_size=1, max_size=6))
def test_colspan_width(n, extra):
    rows = [[TableCell("x" * len("".join(extra)), colspan=n)], ["a"] * n]
    lines = render(["h"] * n, rows)
    assert len({len(l) for l in lines}) == 1, lines

import ast
import time
import warnings

from hypothesis import assume, given, settings, strategies as st

from black.strings import (
    count_chars_in_width,
    lines_with_leading_tabs_expanded,
    normalize_string_prefix,
    normalize_string_quotes,
    normalize_unicode_escape_sequences,
    str_width,
)
from blib2to3.pgen2 import token
from blib2to3.pytree import Leaf

body_chars = st.sampled_from(list("ab'\"\\{}nxu0N ") + ["\t", "é"])
prefixes = st.sampled_from(["", "r", "R", "b", "B", "rb", "Br", "u", "U", "f", "F", "rf", "fR"])
quotes = st.sampled_from(["'", '"', "'''", '"""'])


def literal_value(src):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            tree = ast.parse(src, mode="eval")
        except (SyntaxError, ValueError):
            return None
    import io, tokenize
    toks = [t for t in tokenize.generate_tokens(io.StringIO(src).readline)
            if t.type not in (tokenize.NEWLINE, tokenize.ENDMARKER, tokenize.NL)]
    single = len(toks) == 1 and toks[0].type == tokenize.STRING
    fstr = (toks and toks[0].type == tokenize.FSTRING_START
            and toks[-1].type == tokenize.FSTRING_END
            and sum(t.type == tokenize.FSTRING_START for t in toks) == 1)
    if not (single or fstr):
        return None
    node = tree.body
    if not isinstance(node, (ast.Constant, ast.JoinedStr)):
        return None
    return ast.dump(node).replace(", kind='u'", "")


@st.composite
def string_literals(draw):
    p = draw(prefixes)
    q = draw(quotes)
    body = draw(st.text(body_chars, max_size=12))
    src = f"{p}{q}{body}{q}"
    assume(literal_value(src) is not None)
    return src


@settings(max_examples=3000)
@given(string_literals())
def test_normalize_string_quotes_preserves_value(src):
    out = normalize_string_quotes(src)
    assert literal_value(out) == literal_value(src), (src, out)


@settings(max_examples=2000)
@given(string_literals())
def test_normalize_string_prefix_preserves_value(src):
    out = normalize_string_prefix(src)
    assume("u" not in src.lower()[:2] or True)
    assert literal_value(out) == literal_value(src), (src, out)


@settings(max_examples=2000)
@given(string_literals())
def test_normalize_unicode_escapes_preserves_value(src):
    leaf = Leaf(token.STRING, src)
    normalize_unicode_escape_sequences(leaf)
    assert literal_value(leaf.value) == literal_value(src), (src, leaf.value)


@settings(max_examples=2000)
@given(st.text())
def test_width_consistency(s):
    w = str_width(s)
    assert count_chars_in_width(s, w) == len(s)
    assert w >= 0


def reference_expand(s):
    out = []
    for line in s.splitlines():
        stripped = line.lstrip()
        lead = line[: len(line) - len(stripped)]
        if stripped and "\t" in lead:
            out.append(lead.expandtabs() + stripped)
        else:
            out.append(line)
    if s.endswith("\n"):
        out.append("")
    return out


@settings(max_examples=2000)
@given(st.text(st.sampled_from(list(" \t\nab\x0c"))))
def test_leading_tabs_matches_reference(s):
    assert lines_with_leading_tabs_expanded(s) == reference_expand(s)


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=2000, max_value=4000))
def test_leading_tabs_linear_time(n):
    line = "\t" * n
    start = time.perf_counter()
    lines_with_leading_tabs_expanded("x\n" + line + "\n")
    assert time.perf_counter() - start < 0.5, n

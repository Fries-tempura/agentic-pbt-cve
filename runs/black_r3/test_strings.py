import ast, time
from hypothesis import given, settings, assume, strategies as st, HealthCheck
from black.strings import (normalize_string_quotes, normalize_string_prefix, lines_with_leading_tabs_expanded,
    fix_docstring, str_width, char_width, count_chars_in_width, get_string_prefix)

body_chars = st.sampled_from(list("ab'\"\\{}xn \t"))
prefixes = st.sampled_from(["", "r", "b", "f", "rb", "Rb", "u", "U", "F", "br", "fr", "Rf"])

@st.composite
def string_literals(draw):
    p = draw(prefixes)
    q = draw(st.sampled_from(["'", '"', "'''"]))
    body = "".join(draw(st.lists(body_chars)))
    s = p + q + body + q
    try:
        v = ast.literal_eval(s) if "f" not in p.lower() else compile(s, "<s>", "eval")
    except Exception:
        assume(False)
    import tokenize, io
    try:
        toks=[t for t in tokenize.generate_tokens(io.StringIO(s).readline) if t.type not in (tokenize.NEWLINE, tokenize.ENDMARKER, tokenize.NL)]
    except Exception:
        assume(False)
    assume(len(toks)==1 and toks[0].string==s)
    return s

def value(s):
    if "f" in get_string_prefix(s).lower():
        return ast.dump(ast.parse(s, mode="eval"))
    return ast.literal_eval(s)

@settings(max_examples=3000, suppress_health_check=list(HealthCheck))
@given(string_literals())
def test_quotes_preserve_value(s):
    n = normalize_string_quotes(s)
    assert value(n) == value(s)
    assert normalize_string_quotes(n) == n

@settings(max_examples=2000, suppress_health_check=list(HealthCheck))
@given(string_literals())
def test_prefix_preserve(s):
    n = normalize_string_prefix(s)
    assert value(n) == value(s)

ws = st.text(st.sampled_from(" \t\n\x0b\x0cab"))

@given(ws)
def test_tabs_expanded(s):
    lines = lines_with_leading_tabs_expanded(s)
    assert len(lines) == len(s.splitlines()) + (1 if s.endswith("\n") else 0)
    for a, b in zip(lines, s.splitlines()):
        assert a.strip() == b.strip()

@settings(max_examples=50, deadline=None)
@given(st.integers(100, 1000), st.sampled_from([" \t", "\t", "\t "]))
def test_tabs_expanded_linear_time(n, unit):
    s = unit * n
    t = time.perf_counter()
    lines_with_leading_tabs_expanded(s)
    assert time.perf_counter() - t < 0.1, n

@given(st.text())
def test_str_width(s):
    assert str_width(s) == sum(char_width(c) for c in s)
    k = count_chars_in_width(s, str_width(s))
    assert k == len(s)

@given(st.text(), st.integers(0, 50))
def test_count_chars(s, w):
    k = count_chars_in_width(s, w)
    assert str_width(s[:k]) <= w
    if k < len(s):
        assert str_width(s[:k+1]) > w

@given(st.text(st.sampled_from(" \tab\n")), st.sampled_from(["", "    "]))
def test_fix_docstring_idempotent(d, prefix):
    once = fix_docstring(d, prefix)
    assert fix_docstring(once, prefix) == once

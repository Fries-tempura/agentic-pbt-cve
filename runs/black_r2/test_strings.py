import ast, time, warnings, tokenize, io
from hypothesis import given, settings, assume, strategies as st, HealthCheck
from black.strings import (normalize_string_quotes, normalize_string_prefix, lines_with_leading_tabs_expanded,
    fix_docstring, str_width, count_chars_in_width, char_width)

body_chars = st.sampled_from(list("ab'\"\\{}xn ") )
@st.composite
def string_literals(draw):
    prefix = draw(st.sampled_from(["", "r", "b", "u", "f", "rb", "R", "F", "Rb", "br", "fr", "rf"]))
    q = draw(st.sampled_from(["'", '"', "'''", '"""']))
    body = draw(st.text(body_chars, max_size=12))
    s = prefix + q + body + q
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ast.parse(s, mode="eval")

        toks = [t for t in tokenize.generate_tokens(io.StringIO(s).readline) if t.type not in (tokenize.NEWLINE, tokenize.ENDMARKER)]
        assume(len(toks) == 1 and toks[0].string == s)
    except (SyntaxError, tokenize.TokenError):
        assume(False)
    return s

def value(s):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ast.literal_eval(s) if not s.lower().lstrip("rbu").startswith(("f","rf")) and "f" not in s[:2].lower() else ast.dump(ast.parse(s, mode="eval")).replace(", kind='u'", "")

@settings(max_examples=3000, suppress_health_check=list(HealthCheck))
@given(string_literals())
def test_normalize_quotes_preserves_value(s):
    out = normalize_string_quotes(s)
    assert value(out) == value(s), (s, out)
    assert normalize_string_quotes(out) == out, (s, out)

@settings(max_examples=1000, suppress_health_check=list(HealthCheck))
@given(string_literals())
def test_normalize_prefix_preserves_value(s):
    out = normalize_string_prefix(s)
    assert value(out) == value(s)

def ref_expand(s):
    lines = []
    for line in s.splitlines():
        stripped = line.lstrip()
        ws = line[: len(line) - len(stripped)]
        if stripped and "\t" in ws:
            lines.append(ws.expandtabs() + stripped)
        else:
            lines.append(line)
    if s.endswith("\n"):
        lines.append("")
    return lines

@settings(max_examples=2000)
@given(st.text(st.sampled_from(list(" \t\nab\x0c\r"))))
def test_tabs_expanded_matches_reference(s):
    assert lines_with_leading_tabs_expanded(s) == ref_expand(s)

@settings(max_examples=50, deadline=None)
@given(st.integers(1000, 5000), st.sampled_from(["\t", " \t", "\t "]))
def test_tabs_expanded_linear_time(n, unit):
    s = "x" + unit * n + "\n"  # whitespace-only line with tabs and no non-ws char
    t = time.perf_counter()
    lines_with_leading_tabs_expanded("\t" * n)
    assert time.perf_counter() - t < 1.0

@given(st.text())
def test_width_consistency(s):
    assert str_width(s) == sum(char_width(c) for c in s)
    assert count_chars_in_width(s, str_width(s)) == len(s)

@given(st.text(), st.integers(0, 50))
def test_count_chars_fits(s, w):
    n = count_chars_in_width(s, w)
    assert str_width(s[:n]) <= w
    if n < len(s):
        assert str_width(s[: n + 1]) > w

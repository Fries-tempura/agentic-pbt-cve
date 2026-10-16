import ast, time, warnings
from hypothesis import given, settings, assume, strategies as st, HealthCheck
from blib2to3.pytree import Leaf
from blib2to3.pgen2 import token
from black.strings import (normalize_string_quotes, normalize_string_prefix,
    normalize_unicode_escape_sequences, str_width, char_width, count_chars_in_width,
    lines_with_leading_tabs_expanded, fix_docstring)

warnings.simplefilter("ignore")
prefixes = st.sampled_from(["", "r", "R", "b", "B", "rb", "Rb", "bR", "u", "U", "f", "F", "rf", "fR", "Rf"])
body_chars = st.sampled_from(list("ab'\"\\{}xuN0 \n") )

def lit_eval(s):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return ("ok", ast.literal_eval(s)) if "f" not in s.split(s.lstrip("furbFURB")[:1])[0].lower() else ("ok", ast.dump(ast.parse(s)))
    except Exception:
        return None

@st.composite
def string_literals(draw):
    p = draw(prefixes)
    q = draw(st.sampled_from(["'", '"', "'''", '"""']))
    body = draw(st.text(body_chars, max_size=12))
    s = p + q + body + q
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(s, mode="eval")
    except Exception:
        assume(False)
    assume(isinstance(tree.body, (ast.Constant, ast.JoinedStr)))
    import tokenize, io
    try:
        toks = [t for t in tokenize.generate_tokens(io.StringIO(s).readline) if t.type not in (tokenize.NEWLINE, tokenize.ENDMARKER, tokenize.NL)]
    except Exception:
        assume(False)
    assume(len(toks) == 1 and toks[0].string == s)
    return s

def sem(s):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = ast.parse(s, mode="eval").body
    if isinstance(t, ast.Constant):
        return t.value
    return ast.dump(t)

@settings(max_examples=3000, suppress_health_check=list(HealthCheck))
@given(string_literals())
def test_quotes_preserve_value(s):
    n = normalize_string_quotes(s)
    assert sem(n) == sem(s), (s, n)

@settings(max_examples=3000, suppress_health_check=list(HealthCheck))
@given(string_literals())
def test_quotes_idempotent(s):
    n = normalize_string_quotes(s)
    assert normalize_string_quotes(n) == n

@settings(max_examples=2000, suppress_health_check=list(HealthCheck))
@given(string_literals())
def test_prefix_preserve(s):
    n = normalize_string_prefix(s)
    assert sem(n) == sem(s)

@settings(max_examples=2000, suppress_health_check=list(HealthCheck))
@given(st.sampled_from(["", "b", "u", "f"]), st.text(st.sampled_from(list("\\uUxN{}aAfF09 -")), max_size=20))
def test_unicode_escape_preserve(p, body):
    s = p + '"' + body + '"'
    try:
        v = sem(s)
    except Exception:
        assume(False)
    leaf = Leaf(token.STRING, s)
    normalize_unicode_escape_sequences(leaf)
    assert sem(leaf.value) == v, (s, leaf.value)

@given(st.text())
def test_width(s):
    assert str_width(s) == sum(char_width(c) for c in s)

@given(st.text(), st.integers(0, 50))
def test_count_chars(s, w):
    n = count_chars_in_width(s, w)
    assert str_width(s[:n]) <= w
    if n < len(s):
        assert str_width(s[:n+1]) > w

@given(st.text(st.sampled_from(" \tab\n")))
def test_tabs_lines(s):
    lines = lines_with_leading_tabs_expanded(s)
    assert [l.lstrip() for l in lines][: len(s.splitlines())] == [l.lstrip() for l in s.splitlines()]

def test_tabs_linear_time():
    for n in (2000, 4000, 8000):
        s = "\t" * n + "x" if False else " \t" * n
        t = time.perf_counter(); lines_with_leading_tabs_expanded(s); print(n, time.perf_counter() - t)
    assert time.perf_counter() - t < 1.0

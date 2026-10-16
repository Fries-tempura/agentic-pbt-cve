import ast, time, warnings
from hypothesis import given, settings, assume, strategies as st
from black.strings import (normalize_string_quotes, normalize_string_prefix,
    lines_with_leading_tabs_expanded, fix_docstring, str_width, char_width,
    count_chars_in_width, has_triple_quotes, get_string_prefix)

body_chars = st.sampled_from(list("ab'\"\\{} \tn"))
prefixes = st.sampled_from(["", "r", "b", "rb", "u", "R", "B", "Rb", "br", "U"])

def lit(draw_prefix, quote, body):
    return f"{draw_prefix}{quote}{body}{quote}"

def try_eval(s):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return True, ast.literal_eval(s)
    except Exception:
        return False, None

import io, tokenize
def single_token(s):
    try:
        toks=[t for t in tokenize.generate_tokens(io.StringIO(s).readline) if t.type not in (tokenize.NEWLINE, tokenize.ENDMARKER, tokenize.NL)]
    except Exception:
        return False
    return len(toks)==1 and toks[0].type==tokenize.STRING

@settings(max_examples=3000)
@given(prefixes, st.sampled_from(["'", '"', "'''", '"""']), st.text(body_chars, max_size=12))
def test_quotes_preserve_value(prefix, quote, body):
    s = lit(prefix, quote, body)
    ok, v = try_eval(s)
    assume(ok and single_token(s))
    out = normalize_string_quotes(s)
    ok2, v2 = try_eval(out)
    assert ok2, (s, out)
    assert v == v2, (s, out)
    assert normalize_string_quotes(out) == out

@settings(max_examples=2000)
@given(prefixes, st.sampled_from(["'", '"']), st.text(body_chars, max_size=12))
def test_prefix_preserve_value(prefix, quote, body):
    s = lit(prefix, quote, body)
    ok, v = try_eval(s)
    assume(ok)
    out = normalize_string_prefix(s)
    ok2, v2 = try_eval(out)
    assert ok2 and v == v2, (s, out)

@settings(max_examples=2000)
@given(st.text(st.sampled_from(list(" \ta\n\x0c\r"))))
def test_tabs_expanded(s):
    lines = lines_with_leading_tabs_expanded(s)
    exp = s.splitlines() + ([""] if s.endswith("\n") else [])
    assert len(lines) == len(exp)
    for got, orig in zip(lines, exp):
        assert got.strip() == orig.strip()
        assert "\t" not in got[: len(got) - len(got.lstrip())] or got.strip() == ""

@given(st.integers(1000, 20000))
@settings(max_examples=5, deadline=None)
def test_tabs_perf(n):
    s = "\t" * n
    t = time.perf_counter()
    lines_with_leading_tabs_expanded(s)
    assert time.perf_counter() - t < 1.0

@given(st.text())
def test_width(s):
    assert str_width(s) == sum(char_width(c) for c in s)
    assert count_chars_in_width(s, str_width(s)) == len(s)

@settings(max_examples=1000)
@given(st.text(st.sampled_from(list(" \ta\n"))), st.sampled_from(["", "    "]))
def test_fix_docstring_idempotent(d, p):
    once = fix_docstring(d, p)
    assert fix_docstring(once, p) == once

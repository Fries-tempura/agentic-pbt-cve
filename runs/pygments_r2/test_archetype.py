import time
from hypothesis import given, settings, strategies as st, HealthCheck
from pygments.lexers.archetype import OdinLexer, CadlLexer, AdlLexer

LEXERS = [OdinLexer, CadlLexer, AdlLexer]
alpha = st.sampled_from(list("aZPT0919-._:|[]{}()<>\"' \t\n/\\,;=xX?YyMmDdHhSs+*^@v~"))
text = st.one_of(st.text(), st.text(alpha))

@settings(max_examples=1500, suppress_health_check=list(HealthCheck))
@given(st.sampled_from(LEXERS), text)
def test_roundtrip(lx, s):
    lexer = lx(stripnl=False)
    out = "".join(v for _, v in lexer.get_tokens(s))
    exp = s.replace("\r\n", "\n").replace("\r", "\n")
    if not exp.endswith("\n"):
        exp += "\n"
    assert out == exp

@settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.sampled_from(LEXERS), st.text(alpha, min_size=1, max_size=6), st.integers(500, 2000))
def test_linear_time(lx, unit, n):
    s = unit * n
    t = time.perf_counter()
    list(lx().get_tokens(s))
    assert time.perf_counter() - t < 2.0


def _time(lx, s):
    t = time.perf_counter()
    list(lx().get_tokens(s))
    return time.perf_counter() - t

@settings(max_examples=30, deadline=None)
@given(st.sampled_from([(AdlLexer, ""), (CadlLexer, "[")]),
       st.sampled_from([" ", "\t"]),
       st.sampled_from(["x", "!", "#"]))
def test_whitespace_run_scales_linearly(lx_prefix, ws, tail):
    lx, prefix = lx_prefix
    small = _time(lx, prefix + ws * 2000 + tail)
    big = _time(lx, prefix + ws * 16000 + tail)
    assert big < max(small, 1e-3) * 8 * 3

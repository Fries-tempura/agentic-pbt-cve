import time
from hypothesis import given, settings, strategies as st, HealthCheck
from pygments.lexers.archetype import OdinLexer, CadlLexer, AdlLexer

LEXERS = [OdinLexer, CadlLexer, AdlLexer]
alphabet = st.sampled_from(list("aZ09_-.:/|[](){}<>=,;\"'\\ \t\nPTYMDHSx+*^~%@") + ["--", "archetype", "definition\n", "language\n", "rules\n", "::", "..", "|"])
texts = st.lists(alphabet, max_size=80).map("".join)

@settings(max_examples=2000, suppress_health_check=list(HealthCheck))
@given(st.sampled_from(LEXERS), texts)
def test_roundtrip(cls, text):
    lx = cls(stripnl=False, ensurenl=True)
    out = "".join(v for _, v in lx.get_tokens(text))
    exp = text if text.endswith("\n") else text + "\n"
    assert out == exp

@settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.sampled_from(LEXERS), st.lists(alphabet, min_size=1, max_size=6).map("".join), st.text(alphabet="aP0.-:|[ \n", max_size=5))
def test_linear_time(cls, unit, prefix):
    text = prefix + unit * 3000
    t = time.perf_counter()
    list(cls().get_tokens(text))
    assert time.perf_counter() - t < 2.0, (prefix, unit)

@settings(max_examples=20, deadline=None)
@given(st.sampled_from(["a", "Z", "_", " ", "\t"]))
def test_adl_scales_linearly(ch):
    def t(n):
        s = time.perf_counter(); list(AdlLexer().get_tokens(ch * n + "x")); return time.perf_counter() - s
    small, big = t(2000), t(8000)
    assert big < 8 * max(small, 1e-3), (small, big)

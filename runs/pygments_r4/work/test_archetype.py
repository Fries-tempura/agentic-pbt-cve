import time
from hypothesis import given, settings, strategies as st, HealthCheck
from pygments.lexers.archetype import OdinLexer, CadlLexer, AdlLexer

ALPH = st.sampled_from(list("abcPTYMDHS0123456789 \t\n-_.:;,|[]{}()<>=/\"'\\^*+~@xX?$!") +
                       ["archetype", "definition\n", "language\n", "description\n", "rules\n",
                        "--", "openEHR-EHR-OBSERVATION.bp.v1", "::", "...", "..", "|",
                        "true", "P1Y2M", "2020-01-01T", "12:00:00Z", "0x1F"])
texts = st.one_of(st.text(), st.lists(ALPH).map("".join))

def roundtrip(lexer, text):
    toks = list(lexer.get_tokens(text))
    out = "".join(v for _, v in toks)
    expected = text if text.endswith("\n") else text + "\n"
    # get_tokens normalizes newlines and strips? default stripnl=True
    lx = type(lexer)(stripnl=False, ensurenl=False)
    toks2 = list(lx.get_tokens_unprocessed(text))
    assert "".join(v for _, _, v in toks2) == text
    pos = 0
    for i, _, v in toks2:
        assert i == pos
        pos += len(v)

@settings(max_examples=1500, suppress_health_check=list(HealthCheck), deadline=None)
@given(texts, st.sampled_from([OdinLexer, CadlLexer, AdlLexer]))
def test_roundtrip(text, L):
    roundtrip(L(), text)

@settings(max_examples=300, deadline=None)
@given(st.sampled_from([OdinLexer, CadlLexer, AdlLexer]), st.sampled_from(list(ALPH.wrapped_strategy.elements) if hasattr(ALPH,'wrapped_strategy') else ["a"]), st.integers(500, 3000))
def test_perf_repeat(L, unit, n):
    text = unit * n
    t = time.perf_counter()
    list(L().get_tokens(text))
    assert time.perf_counter() - t < 2.0, (unit, n)

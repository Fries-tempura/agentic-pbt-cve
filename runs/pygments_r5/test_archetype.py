import time
from hypothesis import given, settings, strategies as st
from pygments.lexers.archetype import AdlLexer, CadlLexer, OdinLexer

alphabet = st.sampled_from(list('aZ09_-.:|[]{}()<>/"\'\\ \t\n;,=@^*+PT'))
LEXERS = [AdlLexer, CadlLexer, OdinLexer]

@settings(max_examples=1000)
@given(st.sampled_from(LEXERS), st.text(alphabet))
def test_roundtrip(L, s):
    toks = list(L().get_tokens_unprocessed(s))
    assert ''.join(v for _, _, v in toks) == s

@settings(max_examples=20, deadline=None)
@given(st.sampled_from([AdlLexer]), st.characters(whitelist_categories=['Ll','Lu']),
       st.characters(whitelist_categories=['Ll','Lu','Nd']))
def test_linear_time(L, c1, c2):
    def run(n):
        s = c1 + c2 * n
        t0 = time.perf_counter(); list(L().get_tokens(s)); return time.perf_counter() - t0
    small, big = run(2000), run(20000)
    assert big < 30 * small + 0.05, (small, big)

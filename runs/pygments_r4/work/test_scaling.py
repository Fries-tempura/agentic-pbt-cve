import time
from hypothesis import given, settings, strategies as st
from pygments.lexers.archetype import AdlLexer

def lex_time(s):
    t = time.perf_counter(); list(AdlLexer().get_tokens(s)); return time.perf_counter() - t

@settings(max_examples=10, deadline=None)
@given(st.sampled_from([" ", "\t", "a", "aa.", "x1"]))
def test_adl_lexing_scales_linearly(unit):
    small = lex_time(unit * 2000 + "!")
    big = lex_time(unit * 16000 + "!")
    assert big < 20 * max(small, 0.005), (unit, small, big)

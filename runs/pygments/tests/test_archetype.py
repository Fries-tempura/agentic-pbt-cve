import time
from hypothesis import given, settings, strategies as st
from pygments.lexers.archetype import OdinLexer, CadlLexer, AdlLexer

LEXERS = [OdinLexer(stripnl=False), CadlLexer(stripnl=False), AdlLexer(stripnl=False)]
alphabet = st.sampled_from(list('aZv09_-.:|[](){}<>/"\'\\ \t\n,;=*^+PTYMDHSx@~%'))


@settings(max_examples=500, deadline=None)
@given(st.text(alphabet=alphabet), st.sampled_from(LEXERS))
def test_roundtrip(text, lexer):
    out = ''.join(v for _, v in lexer.get_tokens(text))
    expected = text if text.endswith('\n') else text + '\n'
    assert out == expected


@settings(max_examples=30, deadline=None)
@given(st.integers(500, 3000), st.sampled_from(['a', '0', 'a-']), st.sampled_from(LEXERS))
def test_linear_time(n, ch, lexer):
    text = 'a-a-a.' + ch * n
    t = time.perf_counter()
    list(lexer.get_tokens(text))
    dt = time.perf_counter() - t
    assert dt < 2.0, (n, ch, type(lexer).__name__, dt)

from hypothesis import given, strategies as st
from pygments.lexers.archetype import CadlLexer
from pygments.token import Operator

@given(st.sampled_from(["∃", "∄", "∀", "∧", "∨", "⊻", "∼"]))
def test_logic_operator_chars_are_operators(ch):
    toks = list(CadlLexer().get_tokens(f"a {ch} b"))
    assert (Operator, ch) in toks, toks

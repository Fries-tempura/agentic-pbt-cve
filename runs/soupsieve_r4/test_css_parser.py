import warnings
import soupsieve as sv
from soupsieve import css_parser as cp
from soupsieve.util import SelectorSyntaxError
from bs4 import BeautifulSoup
from hypothesis import given, settings, strategies as st, HealthCheck

warnings.simplefilter("ignore")

# Property 1: compile is a single entry point; on any string it should either succeed
# or raise SelectorSyntaxError / NotImplementedError (documented behaviour).
tokens = st.sampled_from([
    'a', 'div', '*', '|', 'ns|', '.c', '#i', '[x]', '[x="y"]', '[x~=y i]', ':is(', ':not(', ':has(',
    ':where(', ')', ',', ' ', '>', '+', '~', ':nth-child(', '2n+1', ' of ', ':lang(', 'en', ':dir(ltr)',
    ':-soup-contains(', '"t"', ':root', ':empty', ':checked', '\\', '\\31 ', '\\110000', '\\FFFFFF',
    '/*c*/', '&', ':--x', '::before', '@page', "'", '"', '\n', '\x00', 'n', '-',
])

@settings(max_examples=3000, suppress_health_check=[HealthCheck.too_slow])
@given(st.one_of(st.lists(tokens, max_size=15).map(''.join), st.text()))
def test_compile_only_raises_syntax_errors(s):
    try:
        sv.compile(s)
    except (SelectorSyntaxError, NotImplementedError):
        pass


# Property 2: escape() produces an identifier that selects exactly that id.
@settings(max_examples=2000)
@given(st.text(min_size=1).filter(lambda t: '\x00' not in t and '\r' not in t and '\x0c' not in t))
def test_escape_round_trip(ident):
    esc = sv.escape(ident)
    sel = sv.compile('#' + esc)
    assert sel.selectors[0].ids == (ident,)


# Property 3: css_unescape of escaped hex code points yields the code point
@given(st.integers(min_value=1, max_value=0xFFFFFF))
def test_hex_escape_never_crashes(cpnt):
    try:
        sv.compile('#\\%x ' % cpnt)
    except SelectorSyntaxError:
        pass


# Property 4: nesting is bounded by SELECTOR_LIMIT with a clean ValueError/SyntaxError
@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=1, max_value=3000), st.sampled_from([':is(', ':not(', ':where(', ':has(']))
def test_nesting_does_not_recurse_out(depth, p):
    s = p * depth + 'a' + ')' * depth
    try:
        sv.compile(s)
    except (ValueError, SelectorSyntaxError):
        pass

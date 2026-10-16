import warnings
import pytest
from hypothesis import given, settings, strategies as st, assume, HealthCheck
import soupsieve as sv
from soupsieve import css_parser as cp
from soupsieve.util import SelectorSyntaxError

text = st.text(st.characters(blacklist_characters='\x00', blacklist_categories=('Cs',)))


@settings(max_examples=2000)
@given(text)
def test_escape_unescape_roundtrip(s):
    assert cp.css_unescape(cp.escape(s)) == s


@settings(max_examples=1000)
@given(text.filter(lambda s: s))
def test_escape_class_parses(s):
    sl = cp.CSSParser('.' + cp.escape(s)).process_selectors()
    assert sl.selectors[0].classes == (s,)


@settings(max_examples=1000)
@given(text.filter(lambda s: s))
def test_escape_id_and_tag_parses(s):
    sl = cp.CSSParser('#' + cp.escape(s)).process_selectors()
    assert sl.selectors[0].ids == (s,)


@settings(max_examples=500)
@given(st.integers(-1000, 1000), st.integers(-1000, 1000))
def test_nth_parse(a, b):
    sel = f':nth-child({a}n{"+" if b >= 0 else "-"}{abs(b)})'
    sl = cp.CSSParser(sel).process_selectors()
    nth = sl.selectors[0].nth[0]
    assert (nth.a, nth.b, nth.n) == (a, b, True)


tokens = st.sampled_from([
    'div', 'a', '*', '|', 'ns|p', '.c', '#i', '[x]', '[x="y"]', "[x~=y i]", '[x!=1]', ':is(', ':not(', ':has(',
    ':where(', ':nth-child(2n+1', ':nth-child(2n of ', ':nth-of-type(odd)', ':lang(en)', ':dir(ltr)',
    ':-soup-contains("a")', ':checked', ':root', ':hover', ':host(', ')', ',', ' ', '>', '+', '~', '&',
    ':first-child', '/* c */', '\\', ':', '::before', '@page', '"', "'", '(', '[', ']', ':--custom',
])


@settings(max_examples=5000, suppress_health_check=list(HealthCheck))
@given(st.lists(tokens, max_size=20).map(''.join))
def test_parser_only_raises_documented(s):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        try:
            sv.compile(s, namespaces={'ns': 'x'}, custom={':--custom': 'div'})
        except (SelectorSyntaxError, NotImplementedError):
            pass


@pytest.mark.parametrize('name', [':is', ':not', ':has', ':where'])
@pytest.mark.parametrize('depth', [100, 200, 500, 1000, 2000])
def test_deep_nesting(name, depth):
    s = f'{name}(' * depth + 'div' + ')' * depth
    try:
        sv.compile(s)
    except (SelectorSyntaxError, ValueError):
        pass

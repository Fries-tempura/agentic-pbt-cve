import warnings
from hypothesis import given, settings, strategies as st, HealthCheck
import soupsieve as sv
from soupsieve import css_parser as cp
from soupsieve.util import SelectorSyntaxError
from bs4 import BeautifulSoup

ident_text = st.text(st.characters(blacklist_categories=('Cs',)), min_size=1)

@settings(max_examples=2000)
@given(ident_text)
def test_escape_unescape_roundtrip(s):
    s = s.replace('\x00', '�')
    assert cp.css_unescape(cp.escape(s)) == s

@settings(max_examples=1000)
@given(ident_text)
def test_escape_produces_valid_id_selector(s):
    s = s.replace('\x00', '�')
    sel = cp.CSSParser('#' + cp.escape(s)).process_selectors()
    assert sel[0].ids == (s,)

@settings(max_examples=1000)
@given(ident_text)
def test_contains_string_roundtrip(s):
    s = s.replace('\x00', '�')
    # CSS-string-escape every char by codepoint
    esc = ''.join(f'\\{ord(c):x} ' for c in s)
    sel = cp.CSSParser(f':-soup-contains("{esc}")').process_selectors()
    assert list(sel[0].contains[0].text) == [s]

@settings(max_examples=1000)
@given(ident_text)
def test_lang_string_roundtrip(s):
    s = s.replace('\x00', '�')
    esc = ''.join(f'\\{ord(c):x} ' for c in s)
    sel = cp.CSSParser(f':lang("{esc}")').process_selectors()
    assert list(sel[0].lang[0].languages) == [s]

frag = st.sampled_from(['div', 'p', '*', '.a', '#b', '[x]', '[x="y"]', ':is(', ':not(', ':has(', ')', ',', ' ', '>', '+', '~',
                        ':nth-child(2n+1', ':nth-child(odd of ', ':first-child', ':-soup-contains("a")', ':lang(en)', ':where(',
                        ':dir(ltr)', '&', '|', 'ns|a', ':root', '/* c */', '\\', '"', "'", ':', '(', '[', 'n', '-', '2'])

@settings(max_examples=5000, suppress_health_check=list(HealthCheck))
@given(st.lists(frag).map(''.join))
def test_parser_only_raises_syntax_error(s):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        try:
            cp.CSSParser(s).process_selectors()
        except (SelectorSyntaxError, NotImplementedError):
            pass

@settings(max_examples=50, deadline=None)
@given(st.integers(1, 2000), st.sampled_from([':is(', ':not(', ':has(', ':where(']))
def test_nesting_raises_only_documented_errors(n, p):
    try:
        cp.CSSParser(p * n + 'a' + ')' * n).process_selectors()
    except (SelectorSyntaxError, ValueError):
        pass

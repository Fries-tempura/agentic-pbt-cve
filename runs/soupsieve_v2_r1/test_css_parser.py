import time
import pytest
from bs4 import BeautifulSoup
from hypothesis import given, settings, strategies as st
import soupsieve as sv
from soupsieve import css_parser as cp
from soupsieve.util import SelectorSyntaxError

ident_text = st.text(alphabet=st.sampled_from('ab-_09 \\"\'.#:()[]\t\n\x01\x7féあ'), min_size=1, max_size=10)
str_text = st.text(alphabet=st.sampled_from('ab09\\ f'), min_size=1, max_size=8).filter(lambda s: not s.endswith('\\'))


@given(ident_text)
@settings(max_examples=1000)
def test_escape_roundtrip(s):
    """CLAIM-1: parsing '.' + escape(s) yields class s."""
    sl = cp.CSSParser('.' + cp.escape(s)).process_selectors()
    assert sl[0].classes == (s,)


@given(str_text)
@settings(max_examples=500)
def test_contains_single_unescape(s):
    """CLAIM-2: :-soup-contains("S") stores css_unescape(S, True), like :lang."""
    s = s.replace('"', '')
    contains = cp.CSSParser(f':-soup-contains("{s}")').process_selectors()[0].contains[0].text
    lang = cp.CSSParser(f':lang("{s}")').process_selectors()[0].lang[0].languages
    assert lang == (cp.css_unescape(s, True),)
    assert contains == (cp.css_unescape(s, True),)


@given(st.text(alphabet='abc', min_size=1, max_size=5), st.sampled_from(['=', '$=']))
def test_attr_exact_no_trailing_newline(v, op):
    """CLAIM-3: [x="v"] / [x$="v"] must not match x == v + '\\n'."""
    soup = BeautifulSoup('<div></div>', 'html.parser')
    soup.div['x'] = v + '\n'
    assert sv.select(f'div[x{op}"{v}"]', soup) == []


@given(st.integers(min_value=1, max_value=2000))
@settings(max_examples=50, deadline=None)
def test_nesting_no_recursion_error(d):
    """CLAIM-4: deep :is() nesting raises only documented errors."""
    try:
        cp.CSSParser(':is(' * d + 'a' + ')' * d).process_selectors()
    except (ValueError, SelectorSyntaxError):
        pass


@pytest.mark.parametrize('tail', ['b', '!'])
def test_whitespace_linear(tail):
    """CLAIM-5: parse time scales linearly with whitespace length."""
    def t(n):
        s = 'a' + ' ' * n + tail
        st_ = time.perf_counter()
        try:
            cp.CSSParser(s).process_selectors()
        except SelectorSyntaxError:
            pass
        return time.perf_counter() - st_
    small, big = t(2000), t(8000)
    assert big < small * 8


@given(st.integers(min_value=0x110000, max_value=0xFFFFFF), st.sampled_from(['.{}', '#{}', '[x="{}"]', ':lang("{}")']))
def test_large_codepoint_escape(cp_, tmpl):
    """CLAIM-6: escapes above U+10FFFF decode to U+FFFD, no chr() crash."""
    sv.compile(tmpl.format(f'\\{cp_:x}'))

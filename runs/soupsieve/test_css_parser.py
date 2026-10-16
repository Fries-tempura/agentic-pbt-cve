import re
import pytest
from hypothesis import given, settings, strategies as st, assume
import soupsieve as sv
from soupsieve import css_parser as cp
from soupsieve.util import SelectorSyntaxError
from bs4 import BeautifulSoup

idents = st.text(st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00" + "".join(map(chr, range(0x80, 0xa0)))), min_size=1)


@given(idents)
@settings(max_examples=2000)
def test_escape_unescape_roundtrip(s):
    assert cp.css_unescape(cp.escape(s)) == s


@given(idents)
@settings(max_examples=1000)
def test_escaped_id_selector_parses_to_same_id(s):
    sel = cp.CSSParser('#' + cp.escape(s)).process_selectors()
    assert sel.selectors[0].ids == (s,)


@given(idents)
@settings(max_examples=1000)
def test_escaped_class_matches(s):
    soup = BeautifulSoup('<div></div>', 'html.parser')
    soup.div['class'] = [s]
    assume(not re.search(r'[ \t\n\r\f]', s))
    assert sv.select('.' + cp.escape(s), soup) == [soup.div]


SIMPLE = st.sampled_from(['div', 'p', '.a', '#b', '[x]', '[x="y"]', ':first-child', '*', ':not(p)'])
WRAP = st.sampled_from([':is({})', ':not({})', ':where({})', ':has(> {})', ':nth-child(2n+1 of {})'])


@given(st.integers(1, 3000).flatmap(lambda n: st.lists(WRAP, min_size=n, max_size=n)), SIMPLE)
@settings(max_examples=200, deadline=None)
def test_nested_selectors_only_raise_documented_errors(wraps, inner):
    s = inner
    for w in wraps:
        s = w.format(s)
    try:
        cp.CSSParser(s).process_selectors()
    except (SelectorSyntaxError, ValueError):
        pass


@given(st.lists(st.sampled_from(list('abc*.#[]=:()>~+, "\'\\-|nof0123') + [':is(', ':not(', ':has(', ':nth-child(', ':lang(', ':contains(', '/**/']), max_size=40).map(''.join))
@settings(max_examples=5000, deadline=None)
def test_parser_only_raises_documented_errors(s):
    try:
        cp.CSSParser(s).process_selectors()
    except (SelectorSyntaxError, NotImplementedError):
        pass

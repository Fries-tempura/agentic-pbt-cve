import warnings
import pytest
from hypothesis import given, settings, strategies as st, assume
import soupsieve as sv
from soupsieve import css_parser as cp
from soupsieve.util import SelectorSyntaxError
from bs4 import BeautifulSoup

text = st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"), min_size=1)

@settings(max_examples=1000)
@given(text)
def test_escape_unescape_roundtrip(s):
    assert cp.css_unescape(cp.escape(s)) == s

@settings(max_examples=500)
@given(text)
def test_escape_produces_valid_id_selector(s):
    soup = BeautifulSoup('<div></div>', 'html.parser')
    soup.div['id'] = s
    soup.div['class'] = s
    assert sv.select_one('#' + sv.escape(s), soup) is soup.div
    assert sv.select_one('[id="' + s.replace('\\', '\\\\').replace('"', '\\"') + '"]', soup) is soup.div if not any(c in s for c in '\r\n\f') else True

@settings(max_examples=500)
@given(text)
def test_attr_value_escape_roundtrip(s):
    soup = BeautifulSoup('<div></div>', 'html.parser')
    soup.div['data-x'] = s
    sel = '[data-x="' + ''.join('\\' + format(ord(c), 'x') + ' ' for c in s) + '"]'
    assert sv.select_one(sel, soup) is soup.div

@settings(max_examples=500)
@given(text)
def test_contains_value(s):
    soup = BeautifulSoup('<div></div>', 'html.parser')
    soup.div.string = s
    sel = 'div:-soup-contains("' + ''.join('\\' + format(ord(c), 'x') + ' ' for c in s) + '")'
    assert sv.select_one(sel, soup) is soup.div

@settings(max_examples=50, deadline=None)
@given(st.integers(1, 3000), st.sampled_from([':is(', ':not(', ':has(> ', ':where(', ':nth-child(1 of ']))
def test_deep_nesting_no_crash(n, p):
    sel = 'div' + p * n + 'div' + ')' * n
    try:
        sv.compile(sel)
    except (SelectorSyntaxError, ValueError):
        pass

import time
from hypothesis import given, settings, strategies as st
import soupsieve as sv
from soupsieve import css_parser as cp
from soupsieve.util import SelectorSyntaxError

frag = st.sampled_from(['\\a', '\\1', 'a', '-', ' ', '\\', '|', '*', '=', '"', ')', ']', '/**/', '(', ':', 'n', '2'])
prefix = st.sampled_from(['[', '', '.', '#', ':is(', ':nth-child(', ':lang(', '[a=', '[a|'])


@settings(max_examples=300, deadline=None)
@given(p=prefix, parts=st.lists(frag, max_size=30))
def test_compile_cost(p, parts):
    """CLAIM-1: compile returns or raises quickly for short selectors."""
    s = p + ''.join(parts)
    cp._purge_cache()
    t = time.perf_counter()
    try:
        sv.compile(s)
    except (SelectorSyntaxError, NotImplementedError, ValueError):
        pass
    assert time.perf_counter() - t < 1.0, s


idents = st.text(st.characters(codec='utf-8', exclude_categories=['Cs']), min_size=1, max_size=10)


@settings(max_examples=1000)
@given(idents)
def test_escape_roundtrip_selector(x):
    """CLAIM-2: '.' + escape(x) parses and yields class x."""
    sel = sv.compile('.' + sv.escape(x))
    assert sel.selectors[0].classes == (x.replace('\0', '�'),)


@settings(max_examples=1000)
@given(idents)
def test_escape_unescape(x):
    """CLAIM-3: css_unescape inverts escape."""
    assert cp.css_unescape(sv.escape(x)) == x.replace('\0', '�')


unit = st.sampled_from(['\\a', '\\1', '\\f', 'a', '\\a ', '-'])


@settings(max_examples=60, deadline=None)
@given(p=prefix, u=unit, n=st.integers(0, 25), tail=st.sampled_from(['', '!', ')', '|']))
def test_compile_cost_repeated(p, u, n, tail):
    """CLAIM-1: compile returns or raises quickly; repeated identifier units."""
    s = p + u * n + tail
    cp._purge_cache()
    t = time.perf_counter()
    try:
        sv.compile(s)
    except (SelectorSyntaxError, NotImplementedError, ValueError):
        pass
    assert time.perf_counter() - t < 1.0, repr(s)

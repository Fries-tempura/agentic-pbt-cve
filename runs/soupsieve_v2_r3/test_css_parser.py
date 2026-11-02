import time
import warnings

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

import soupsieve as sv
from soupsieve import css_parser as cp
from soupsieve.util import SelectorSyntaxError


@settings(max_examples=60, deadline=None)
@given(depth=st.integers(min_value=1, max_value=2000),
       pseudo=st.sampled_from([':is(', ':not(', ':where(', ':has(> ']))
def test_nesting_below_limit_compiles(depth, pseudo):
    """CLAIM-1: nested selectors with count well below SELECTOR_LIMIT never raise RecursionError."""
    sel = pseudo * depth + 'a' + ')' * depth
    sv.purge()
    try:
        sv.compile(sel)
    except (SelectorSyntaxError, ValueError):
        pass  # documented failure modes


@settings(max_examples=300)
@given(cp_=st.integers(min_value=0, max_value=0xFFFFFF))
def test_hex_escape_never_raises(cp_):
    """CLAIM-2: any 1-6 hex digit escape is unescaped without raising."""
    esc = '\\' + format(cp_, 'x')
    out = cp.css_unescape(esc)
    if cp_ > 0x10FFFF:
        assert out == '�'
    sv.compile('.a' + esc + ' ')


@settings(max_examples=1000)
@given(s=st.text(min_size=1).filter(lambda s: '\x00' not in s))
def test_escape_round_trip(s):
    """CLAIM-3: compile('.' + escape(s)) yields class s."""
    sel = sv.compile('.' + cp.escape(s)).selectors[0]
    assert sel.classes == (s,)


@settings(max_examples=500)
@given(a=st.integers(-10**6, 10**6), b=st.integers(-10**6, 10**6))
def test_nth_parse(a, b):
    """CLAIM-4: :nth-child(An+B) parses to a == A, b == B."""
    sign = '+' if b >= 0 else '-'
    sel = sv.compile(f':nth-child({a}n{sign}{abs(b)})').selectors[0]
    nth = sel.nth[0]
    assert (nth.a, nth.n, nth.b) == (a, True, b)


@settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck))
@given(s=st.text(alphabet=' \t\n/*()[]:,>+~.#="\'\\aisn-0|', min_size=0, max_size=2000))
def test_parse_time(s):
    """CLAIM-5: parsing/rejecting a selector is fast."""
    sv.purge()
    t = time.perf_counter()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        try:
            sv.compile(s)
        except (SelectorSyntaxError, ValueError, NotImplementedError, RecursionError):
            pass
    assert time.perf_counter() - t < 2.0


@pytest.mark.parametrize('pattern', ['/*' + '*' * 3000, ' ' * 3000 + 'a' + ' /**/' * 2000 + 'x', 'a' + ' ' * 5000 + ',', '[a' + ' ' * 3000])
def test_parse_time_adversarial(pattern):
    """CLAIM-5: hand-built adversarial inputs for the nested WSC/COMMENTS quantifiers."""
    sv.purge()
    t = time.perf_counter()
    try:
        sv.compile(pattern)
    except (SelectorSyntaxError, ValueError):
        pass
    assert time.perf_counter() - t < 2.0

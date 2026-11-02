import time

import pytest
import soupsieve as sv
from hypothesis import given, settings, strategies as st, HealthCheck
from soupsieve import css_parser as cp
from soupsieve.util import SelectorSyntaxError


def parse(s):
    return cp.CSSParser(s).process_selectors()


def cost(s):
    t = time.perf_counter()
    try:
        parse(s)
    except (SelectorSyntaxError, NotImplementedError, ValueError):
        pass
    return time.perf_counter() - t


# Building blocks the tokenizer treats specially: identifier chars, whitespace, comments,
# and characters that terminate/break tokens.
UNIT = st.sampled_from(['a', '-', ' ', '\t', '/**/', '\\41 ', '!', '.', '#', ',', ':'])


@settings(max_examples=40, deadline=None, suppress_health_check=list(HealthCheck))
@given(prefix=st.lists(UNIT, max_size=3).map(''.join),
       unit=st.lists(UNIT, min_size=1, max_size=3).map(''.join),
       suffix=st.lists(UNIT, max_size=3).map(''.join))
def test_linear_cost(prefix, unit, suffix):
    """CLAIM-1: parse cost grows linearly with selector length."""
    n = 1000
    small = prefix + unit * n + suffix
    big = prefix + unit * (4 * n) + suffix
    t_small = max(min(cost(small) for _ in range(2)), 1e-3)
    t_big = min(cost(big) for _ in range(2))
    # Linear => ratio ~4; quadratic => ~16.
    assert t_big / t_small < 10 or t_big < 0.05, (repr(unit), t_small, t_big)


@given(st.integers(min_value=0, max_value=0xFFFFFF))
def test_unescape_hex_no_crash(cp_):
    """CLAIM-2: any 1-6 digit hex escape unescapes without raising."""
    assert isinstance(cp.css_unescape('\\%x' % cp_), str)


@given(st.integers(min_value=1, max_value=0xFFFFFF))
def test_compile_hex_escape_no_crash(cp_):
    """CLAIM-2: an accepted escaped class selector compiles or raises SelectorSyntaxError."""
    try:
        sv.compile('.\\%x' % cp_)
    except SelectorSyntaxError:
        pass


@given(st.text(min_size=1).filter(lambda s: '\x00' not in s))
def test_escape_round_trip(s):
    """CLAIM-3: '.' + escape(s) parses to a class selector named s."""
    sl = parse('.' + cp.escape(s))
    assert len(sl) == 1
    assert sl[0].classes == (s,)


WSC = st.lists(st.sampled_from([' ', '\t', '\n', '\r\n', '\f', '/* c */', '/**/']), max_size=4).map(''.join)


@given(sel=st.sampled_from(['a', 'div > p', '.x', '#y', 'a:is(b, c)', '[href]', 'p ~ a', 'a:nth-child(2n+1)']),
       ws1=WSC, ws2=WSC)
def test_surrounding_ws_ignored(sel, ws1, ws2):
    """CLAIM-4: leading/trailing whitespace and comments do not change the parse."""
    assert parse(ws1 + sel + ws2) == parse(sel)


@settings(max_examples=2000)
@given(st.text(min_size=1).filter(lambda s: not any(c == '\x00' or '\x80' <= c <= '\x9f' for c in s)))
def test_escape_round_trip_excluding_c1(s):
    """CLAIM-3: round trip, with the already-reported C1 range excluded to look for other failures."""
    sl = parse('.' + cp.escape(s))
    assert len(sl) == 1
    assert sl[0].classes == (s,)

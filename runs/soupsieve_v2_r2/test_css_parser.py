import time
from hypothesis import given, settings, strategies as st, HealthCheck
import soupsieve as sv
from soupsieve import css_parser as cp
from soupsieve.util import SelectorSyntaxError

ALLOWED = (SelectorSyntaxError, ValueError, NotImplementedError)


def _time(p):
    cp._purge_cache()
    s = time.perf_counter()
    try:
        sv.compile(p)
    except ALLOWED:
        pass
    return time.perf_counter() - s


@settings(max_examples=20, deadline=None, suppress_health_check=list(HealthCheck))
@given(ws=st.sampled_from([' ', '\t', '\n', '/**/']),
       tail=st.sampled_from(['b', '!', '>b', '', ')']),
       head=st.sampled_from(['a', '[x', ':is(a', 'div.c']))
def test_linear_time(ws, head, tail):
    """CLAIM-1: compile time is roughly linear in the length of a whitespace run."""
    n = 3000
    t1 = _time(head + ws * n + tail)
    t2 = _time(head + ws * (2 * n) + tail)
    assert t2 < 0.05 or t2 / max(t1, 1e-3) < 3.0, (t1, t2)


@settings(max_examples=60, deadline=None)
@given(depth=st.integers(1, 2000),
       pseudo=st.sampled_from([':is(', ':not(', ':where(', ':has(> ']),
       closed=st.booleans())
def test_only_documented_exceptions(depth, pseudo, closed):
    """CLAIM-2: compile raises only SelectorSyntaxError/ValueError/NotImplementedError."""
    p = pseudo * depth + 'a' + (')' * depth if closed else '')
    cp._purge_cache()
    try:
        sv.compile(p)
    except ALLOWED:
        pass


@settings(max_examples=500)
@given(st.text(min_size=1).filter(lambda s: '\x00' not in s))
def test_escape_round_trip(s):
    """CLAIM-3: '.' + escape(s) parses back to class s."""
    sel = cp.CSSParser('.' + sv.escape(s)).process_selectors()
    assert sel.selectors[0].classes == (s,)

import time
from hypothesis import given, settings, strategies as st
from configobj.validate import Validator

@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=0, max_value=30000))
def test_check_parsing_is_not_superlinear(i):
    """Parsing a check string should take time roughly linear in its length.
    The Validator advertises no size limit on check strings; parse cost must
    not explode on adversarial (but short) inputs."""
    v = Validator()
    attack = '\x00' * i + ')' + '(' * i
    t = time.perf_counter()
    try:
        v.check(attack, 'aaa')
    except Exception:
        pass
    elapsed = time.perf_counter() - t
    # ~0.5s already at len 32001; linear parsing would be sub-millisecond.
    assert elapsed < 0.5, 'len=%d took %.2fs (super-linear backtracking)' % (len(attack), elapsed)

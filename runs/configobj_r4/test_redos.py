import time
from hypothesis import given, settings, strategies as st, HealthCheck
from configobj.validate import Validator, VdtParamError

pieces = st.sampled_from(['a', '=', ',', ' ', '(', ')', '"', "'", 'list(', 'a=', '\t', 'x '])

@settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck))
@given(prefix=st.lists(pieces, max_size=4), unit=st.lists(pieces, min_size=1, max_size=3),
       suffix=st.lists(pieces, max_size=3))
def test_parse_check_scales(prefix, unit, suffix):
    body = ''.join(prefix) + ''.join(unit) * 25 + ''.join(suffix)
    check = 'string(%s)' % body
    t = time.perf_counter()
    try:
        Validator()._parse_check(check)
    except VdtParamError:
        pass
    assert time.perf_counter() - t < 1.0, repr(check)

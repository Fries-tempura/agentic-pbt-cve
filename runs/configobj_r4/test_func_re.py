import time
from hypothesis import given, settings, strategies as st, HealthCheck
from configobj.validate import Validator, ValidateError, VdtParamError

@settings(max_examples=50, deadline=None, suppress_health_check=list(HealthCheck))
@given(unit=st.text(alphabet='a(=, ', min_size=1, max_size=3).filter(lambda u: '(' in u),
       n=st.integers(5000, 20000))
def test_check_parse_time_linearish(unit, n):
    check = unit * n
    t = time.perf_counter()
    try:
        Validator().check(check, '1')
    except (ValidateError, VdtParamError):
        pass
    assert time.perf_counter() - t < 0.5, (repr(unit), n, time.perf_counter() - t)

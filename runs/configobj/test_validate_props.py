"""Property-based tests for configobj.validate."""
import string

import pytest
from hypothesis import assume, given, settings, strategies as st

from configobj.validate import (
    Validator,
    ValidateError,
    VdtParamError,
    dottedQuadToNum,
    numToDottedQuad,
    is_float,
    is_integer,
    is_list,
    is_string,
)

# ---------------------------------------------------------------- IP helpers

MAXIP = 4294967295


@given(st.integers(min_value=0, max_value=MAXIP))
def test_num_to_quad_round_trip(n):
    """Documented inverse pair: dottedQuadToNum / numToDottedQuad."""
    assert dottedQuadToNum(numToDottedQuad(n)) == n


@given(st.lists(st.integers(min_value=0, max_value=255), min_size=4, max_size=4))
def test_quad_to_num_round_trip(octets):
    s = '.'.join(str(o) for o in octets)
    assert numToDottedQuad(dottedQuadToNum(s)) == s


# ------------------------------------------------------- numeric conversions


@given(st.integers())
def test_is_integer_string_round_trip(n):
    """'If the value is a string, then the conversion is done'."""
    assert is_integer(str(n)) == n


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_is_float_string_round_trip(f):
    assert is_float(repr(f)) == f


@given(
    st.floats(allow_infinity=True, allow_nan=True),
    st.floats(allow_nan=False, allow_infinity=False),
    st.floats(allow_nan=False, allow_infinity=False),
)
def test_is_float_result_within_bounds(value, lo, hi):
    """is_float checks 'that it is between bounds' -- so a returned value must be."""
    assume(lo <= hi)
    try:
        result = is_float(value, lo, hi)
    except ValidateError:
        return
    assert lo <= result <= hi


@given(
    st.integers(),
    st.integers(),
    st.integers(),
)
def test_is_integer_result_within_bounds(value, lo, hi):
    assume(lo <= hi)
    try:
        result = is_integer(value, lo, hi)
    except ValidateError:
        return
    assert lo <= result <= hi


# ------------------------------------------------------------- length checks


@given(st.lists(st.integers()), st.integers(min_value=0, max_value=20),
       st.integers(min_value=0, max_value=20))
def test_is_list_length_bounds(value, lo, hi):
    assume(lo <= hi)
    try:
        result = is_list(value, lo, hi)
    except ValidateError:
        return
    assert lo <= len(result) <= hi
    assert result == list(value)


@given(st.text(), st.integers(min_value=0, max_value=20),
       st.integers(min_value=0, max_value=20))
def test_is_string_length_bounds(value, lo, hi):
    assume(lo <= hi)
    try:
        result = is_string(value, lo, hi)
    except ValidateError:
        return
    assert lo <= len(result) <= hi
    assert result == value


# ------------------------------------------------------- check-string parsing

SAFE = st.text(
    alphabet=string.ascii_letters + string.digits + ' _-.\n+',
    min_size=1,
    max_size=8,
)


@given(st.lists(SAFE, min_size=1, max_size=4, unique=True))
def test_option_round_trip(options):
    """Every option listed in an option() check must validate as itself."""
    v = Validator()
    check = 'option(%s)' % ', '.join('"%s"' % o for o in options)
    for o in options:
        assert v.check(check, o) == o


@given(SAFE)
def test_string_default_round_trip(text):
    """get_default_value must give back the quoted default verbatim."""
    v = Validator()
    assert v.get_default_value('string(default="%s")' % text) == text


@given(SAFE)
def test_check_missing_matches_get_default_value(text):
    v = Validator()
    check = 'string(default="%s")' % text
    assert v.check(check, '', missing=True) == v.get_default_value(check)


@given(st.lists(
    st.text(alphabet=string.ascii_letters + string.digits, min_size=1, max_size=5),
    min_size=1, max_size=4))
def test_default_list_is_not_shared_between_calls(items):
    """Validator caches parsed checks but documents working on *copies*
    (see _parse_with_caching) -- a list default must not leak between calls."""
    v = Validator()
    check = 'pass(default=list(%s))' % ', '.join(items)
    first = v.get_default_value(check)
    expected = list(first)
    first.append('MUTATED')
    second = v.get_default_value(check)
    assert second == expected


@given(st.lists(st.integers(min_value=0, max_value=100), min_size=3, max_size=6))
def test_bad_arity_raises_vdt_param_error(args):
    """'A badly formatted set of arguments will raise a VdtParamError.'"""
    v = Validator()
    check = 'integer(%s)' % ', '.join(str(a) for a in args)
    try:
        v.check(check, '5')
    except (ValidateError, VdtParamError):
        pass

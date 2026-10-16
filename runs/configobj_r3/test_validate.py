import time
from hypothesis import given, settings, strategies as st, assume
from configobj.validate import (Validator, VdtParamError, ValidateError,
                                 is_integer, is_float, is_boolean, VdtValueTooSmallError,
                                 VdtValueTooBigError)

def capture(value, *args, **kwargs):
    return args, kwargs

ident = st.from_regex(r'\A[a-zA-Z_][a-zA-Z0-9_]{0,8}\Z')
# plain unquoted values: no quotes, commas, equals, parens, whitespace
plain = st.text(alphabet='abcXYZ019.-_', min_size=1, max_size=10).filter(lambda s: s[0] not in "'\"")
quoted_val = st.text(alphabet=st.characters(blacklist_characters='"\'', blacklist_categories=('Cs',)), max_size=10).map(lambda s: '"%s"' % s)

@settings(max_examples=500)
@given(st.lists(st.one_of(plain, quoted_val), max_size=5),
       st.dictionaries(ident.filter(lambda k: k != 'default'), st.one_of(plain, quoted_val), max_size=4))
def test_parse_round_trip(args, kwargs):
    v = Validator({'cap': capture})
    parts = list(args) + ['%s=%s' % (k, val) for k, val in kwargs.items()]
    check = 'cap(%s)' % ', '.join(parts)
    got_args, got_kwargs = v.check(check, 'x')
    unq = lambda s: s[1:-1] if s.startswith('"') else s
    assert list(got_args) == [unq(a) for a in args]
    assert got_kwargs == {k: unq(val) for k, val in kwargs.items()}


@settings(max_examples=200, deadline=None)
@given(st.text(alphabet='a(),=\'" ', max_size=40), st.integers(min_value=1, max_value=5))
def test_parse_terminates_fast(s, rep):
    v = Validator()
    check = s * (1 + 2000 // max(1, len(s)))
    t = time.perf_counter()
    try:
        v._parse_check(check)
    except VdtParamError:
        pass
    assert time.perf_counter() - t < 1.0, repr(s)


@given(st.integers(), st.one_of(st.none(), st.integers()), st.one_of(st.none(), st.integers()))
def test_integer_bounds(x, lo, hi):
    try:
        r = is_integer(str(x), lo, hi)
        assert r == x
        assert (lo is None or x >= lo) and (hi is None or x <= hi)
    except VdtValueTooSmallError:
        assert x < lo
    except VdtValueTooBigError:
        assert x > hi


@given(st.sampled_from(['on','1','true','yes','off','0','false','no']), st.data())
def test_boolean_case_insensitive(s, data):
    mixed = ''.join(c.upper() if data.draw(st.booleans()) else c for c in s)
    assert is_boolean(mixed) == is_boolean(s)

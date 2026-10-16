import time
from hypothesis import given, settings, strategies as st, assume
from configobj.validate import (Validator, is_integer, is_float, is_boolean,
                                is_ip_addr, VdtValueTooSmallError,
                                VdtValueTooBigError, VdtParamError, ValidateError)

ident = st.from_regex(r'[a-zA-Z_][a-zA-Z0-9_]{0,8}', fullmatch=True)
plain = st.from_regex(r'[a-zA-Z0-9_.+-]{1,10}', fullmatch=True).filter(lambda s: s.strip() == s)
quoted_body = st.text(alphabet=st.characters(blacklist_characters='"\'', blacklist_categories=('Cs',)), max_size=10)
value = st.one_of(plain, quoted_body.map(lambda s: '"%s"' % s))

def unq(v):
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'' else v


@settings(max_examples=500, deadline=None)
@given(name=ident, args=st.lists(value, max_size=4),
       kwargs=st.dictionaries(ident.filter(lambda k: k != 'default'), value, max_size=3),
       lists=st.dictionaries(ident.filter(lambda k: k != 'default'), st.lists(value, max_size=4), max_size=2))
def test_parse_check_roundtrip(name, args, kwargs, lists):
    assume(not set(kwargs) & set(lists))
    parts = list(args) + ['%s=%s' % kv for kv in kwargs.items()] + \
        ['%s=list(%s)' % (k, ', '.join(v)) for k, v in lists.items()]
    check = '%s(%s)' % (name, ', '.join(parts))
    v = Validator()
    fname, fargs, fkw, default = v._parse_check(check)
    assert fname == name
    assert fargs == [unq(a) for a in args]
    for k, val in kwargs.items():
        exp = val if val in ("'None'", '"None"') else unq(val)
        assert fkw[k] == exp
    for k, vals in lists.items():
        assert fkw[k] == [unq(x) for x in vals]


@settings(max_examples=200, deadline=None)
@given(st.text(alphabet='a(=,)\'" \tl ist', min_size=0, max_size=40), st.integers(1, 3))
def test_parse_check_terminates_fast(body, reps):
    check = 'string(%s)' % (body * reps)
    v = Validator()
    t = time.perf_counter()
    try:
        v._parse_check(check)
    except VdtParamError:
        pass
    assert time.perf_counter() - t < 0.5, (check, time.perf_counter() - t)


@given(st.integers(), st.integers(), st.integers())
def test_is_integer_bounds(x, lo, hi):
    try:
        r = is_integer(str(x), min=str(lo), max=str(hi))
    except VdtValueTooSmallError:
        assert x < lo; return
    except VdtValueTooBigError:
        assert x > hi; return
    assert r == x and lo <= x <= hi


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_is_float_str(x):
    assert is_float(repr(x)) == x


@given(st.tuples(*[st.integers(0, 255)] * 4))
def test_ip_addr_valid(q):
    s = '.'.join(map(str, q))
    assert is_ip_addr(s) == s


@given(st.sampled_from(['on', 'off', '1', '0', 'true', 'false', 'yes', 'no']), st.data())
def test_is_boolean_case(word, data):
    mixed = ''.join(data.draw(st.sampled_from([c.lower(), c.upper()])) for c in word)
    assert is_boolean(mixed) == is_boolean(word)


@settings(max_examples=300, deadline=None)
@given(name=st.sampled_from(['integer', 'string', 'float']), d=plain)
def test_default_value_matches_check(name, d):
    v = Validator()
    chk = '%s(default=%s)' % (name, d)
    try:
        expected = v.check(name, d)
    except ValidateError:
        return
    assert v.get_default_value(chk) == expected
    assert v.check(chk, None, missing=True) == expected

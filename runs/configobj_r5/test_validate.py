import time
from hypothesis import given, settings, strategies as st, assume
from configobj.validate import (Validator, dottedQuadToNum, numToDottedQuad,
    is_integer, is_float, is_boolean, VdtParamError, ValidateError)

ident = st.from_regex(r'\A[a-zA-Z_][a-zA-Z0-9_]{0,8}\Z')
# plain unquoted values: no quotes, commas, equals, parens, whitespace
plain = st.text(alphabet='abcxyz0123456789._-', min_size=1, max_size=10)
quoted = st.text(alphabet='abc 0123,=()', max_size=10).map(lambda s: '"%s"' % s)

def capture(value, *args, **kw):
    return args, kw

@given(st.lists(plain, max_size=5), st.dictionaries(ident, plain, max_size=4))
@settings(max_examples=500)
def test_check_parse_roundtrip(args, kwargs):
    assume('default' not in kwargs)
    v = Validator({'cap': capture})
    parts = list(args) + ['%s=%s' % kv for kv in kwargs.items()]
    s = 'cap(%s)' % ', '.join(parts)
    a, kw = v.check(s, None if False else 'x')
    assert list(a) == args
    assert kw == kwargs

@given(st.lists(quoted, max_size=5))
def test_check_parse_quoted(args):
    v = Validator({'cap': capture})
    s = 'cap(%s)' % ', '.join(args)
    a, kw = v.check(s, 'x')
    assert list(a) == [x[1:-1] for x in args]

@given(st.text(max_size=30))
@settings(max_examples=1000)
def test_check_parse_no_crash(argstr):
    v = Validator({'cap': capture})
    try:
        v.check('cap(%s)' % argstr, 'x')
    except (VdtParamError, ValidateError):
        pass

@given(st.text(alphabet='a ,=\'"()', max_size=40))
@settings(max_examples=500, deadline=None)
def test_check_parse_fast(argstr):
    v = Validator({'cap': capture})
    t = time.perf_counter()
    try:
        v.check('cap(%s)' % argstr, 'x')
    except Exception:
        pass
    assert time.perf_counter() - t < 0.5

@given(st.integers(0, 2**32 - 1))
def test_ip_roundtrip(n):
    assert dottedQuadToNum(numToDottedQuad(n)) == n

@given(st.integers(), st.integers(), st.integers())
def test_integer_bounds(x, lo, hi):
    v = Validator()
    try:
        r = v.check('integer(min=%d, max=%d)' % (lo, hi), str(x))
        assert lo <= r <= hi and r == x
    except ValidateError:
        assert not (lo <= x <= hi)

@given(st.lists(plain, min_size=1, max_size=5))
def test_list_default(items):
    v = Validator({'cap': capture})
    s = 'cap(default=list(%s))' % ', '.join(items)
    assert v.get_default_value('string_list(default=list(%s))' % ', '.join(items)) == items

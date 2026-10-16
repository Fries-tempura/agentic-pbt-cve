import time

from hypothesis import given, settings, strategies as st

from configobj.validate import (
    Validator, VdtValueTooBigError, VdtValueTooSmallError, ValidateError,
    dottedQuadToNum, numToDottedQuad, _test,
)

octet = st.integers(0, 255)


@given(st.integers(0, 2**32 - 1))
def test_ip_num_roundtrip(n):
    assert dottedQuadToNum(numToDottedQuad(n)) == n


@given(octet, octet, octet, octet)
def test_ip_str_roundtrip(a, b, c, d):
    ip = "%d.%d.%d.%d" % (a, b, c, d)
    assert numToDottedQuad(dottedQuadToNum(ip)) == ip
    assert Validator().check("ip_addr", ip) == ip


# quoted arguments: any text not containing the quote char
dq = st.text(st.characters(blacklist_characters='"', blacklist_categories=("Cs",)))
sq = st.text(st.characters(blacklist_characters="'", blacklist_categories=("Cs",)))
quoted = st.one_of(dq.map(lambda s: (s, '"%s"' % s)), sq.map(lambda s: (s, "'%s'" % s)))


@given(st.lists(quoted, min_size=1))
def test_option_roundtrip(opts):
    v = Validator()
    spec = "option(%s)" % ", ".join(q for _, q in opts)
    for raw, _ in opts:
        assert v.check(spec, raw) == raw


@given(st.lists(quoted), st.dictionaries(st.from_regex(r"[a-z_][a-z0-9_]{0,5}", fullmatch=True), quoted))
def test_parse_args_kwargs(args, kwargs):
    kwargs.pop("default", None)
    v = Validator({"test": _test})
    parts = [q for _, q in args] + ["%s=%s" % (k, q) for k, (_, q) in kwargs.items()]
    spec = "test(%s)" % ", ".join(parts)
    value, got_args, got_kwargs = v.check(spec, 3)
    assert list(got_args) == [r for r, _ in args]
    assert got_kwargs == {k: r for k, (r, _) in kwargs.items()}


@given(quoted)
def test_default_roundtrip(q):
    raw, quoted_str = q
    if raw == "None":
        return
    v = Validator()
    assert v.get_default_value("string(default=%s)" % quoted_str) == raw
    assert v.check("string(default=%s)" % quoted_str, None, missing=True) == raw


@given(st.integers(), st.integers(), st.integers())
def test_integer_bounds(lo, hi, x):
    v = Validator()
    spec = "integer(%d, %d)" % (lo, hi)
    try:
        r = v.check(spec, str(x))
    except VdtValueTooSmallError:
        assert x < lo
    except VdtValueTooBigError:
        assert x > hi
    else:
        assert r == x and lo <= x <= hi


@given(st.integers(min_value=-(10**400), max_value=10**400))
def test_float_accepts_ints(x):
    # docstring: "a float (an integer will be accepted)"; failures must be ValidateError
    try:
        Validator().check("float", x)
    except ValidateError:
        pass


@settings(max_examples=60, deadline=None)
@given(st.text(alphabet="(),=\"' ab", min_size=1, max_size=4), st.integers(500, 3000))
def test_parse_is_fast(chunk, n):
    spec = chunk * n
    t = time.perf_counter()
    try:
        Validator().check(spec, "x")
    except (ValidateError, SyntaxError, TypeError):
        pass
    assert time.perf_counter() - t < 1.0, (chunk, n)

"""Sanity-check the proposed patches against the module's own doctests."""
import doctest
import inspect
import sys

from configobj import validate as V

# --- fix 1: nan must not slip through bounds -------------------------------
_orig_is_float = V.is_float


def is_float(value, min=None, max=None):
    (min_val, max_val) = V._is_num_param(('min', 'max'), (min, max), to_float=True)
    if not isinstance(value, (int, float, V.string_type)):
        raise V.VdtTypeError(value)
    if not isinstance(value, float):
        try:
            value = float(value)
        except ValueError:
            raise V.VdtTypeError(value)
    if (min_val is not None) and not (value >= min_val):
        raise V.VdtValueTooSmallError(value)
    if (max_val is not None) and not (value <= max_val):
        raise V.VdtValueTooBigError(value)
    return value


# --- fix 2: copy list defaults out of the cache ----------------------------
def _parse_with_caching(self, check):
    if check in self._cache:
        fun_name, fun_args, fun_kwargs, default = self._cache[check]
        fun_args = list(fun_args)
        fun_kwargs = dict(fun_kwargs)
    else:
        fun_name, fun_args, fun_kwargs, default = self._parse_check(check)
        fun_kwargs = dict([(str(k), v) for (k, v) in list(fun_kwargs.items())])
        self._cache[check] = fun_name, list(fun_args), dict(fun_kwargs), default
    if isinstance(default, list):
        default = list(default)
    return fun_name, fun_args, fun_kwargs, default


# --- fix 3: arity/keyword mistakes become VdtParamError --------------------
def _check_value(self, value, fun_name, fun_args, fun_kwargs):
    try:
        fun = self.functions[fun_name]
    except KeyError:
        raise V.VdtUnknownCheckError(fun_name)
    try:
        inspect.signature(fun).bind(value, *fun_args, **fun_kwargs)
    except TypeError as e:
        raise V.VdtParamError(fun_name, e)
    return fun(value, *fun_args, **fun_kwargs)


V.is_float = is_float
V.fun_dict['float'] = is_float
V.Validator._parse_with_caching = _parse_with_caching
V.Validator._check_value = _check_value

vtor = V.Validator()
vtor.functions['float'] = is_float

# the three bugs are gone
for bad in ('float(0, 1)', 'float(min=0)'):
    try:
        vtor.check(bad, 'nan')
        print('FAIL nan still accepted by', bad)
    except V.VdtValueError:
        pass

c = "pass(default=list('a', 'b'))"
f = vtor.get_default_value(c)
f.append('MUTATED')
assert vtor.get_default_value(c) == ['a', 'b'], 'FAIL default still shared'

for bad in ('integer(1, 2, 3)', 'integer(bogus=1)'):
    try:
        vtor.check(bad, '5')
        print('FAIL no error for', bad)
    except V.VdtParamError:
        pass

globs = V.__dict__.copy()
globs['vtor'] = vtor
failures, tests = doctest.testmod(
    V, globs=globs,
    optionflags=doctest.IGNORE_EXCEPTION_DETAIL | doctest.ELLIPSIS)
print('doctests: {} failures out of {}'.format(failures, tests))
sys.exit(0)

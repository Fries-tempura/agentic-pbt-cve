import doctest

from configobj import validate as V


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


is_float.__doc__ = V.is_float.__doc__
vtor = V.Validator()
vtor.functions['float'] = is_float

globs = dict(V.__dict__)
globs['vtor'] = vtor
r = doctest.DocTestRunner(
    optionflags=doctest.IGNORE_EXCEPTION_DETAIL | doctest.ELLIPSIS)
for x in doctest.DocTestFinder().find(is_float, globs=globs, name='is_float'):
    r.run(x)
print('patched is_float doctests:', r.summarize())
for bad in ('float(0, 1)', 'float(min=0)', 'float(max=1)'):
    try:
        print('LEAK', bad, vtor.check(bad, 'nan'))
    except V.VdtValueError as e:
        print('rejected', bad, '->', type(e).__name__)

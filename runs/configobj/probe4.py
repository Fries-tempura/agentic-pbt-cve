from configobj import validate as V

vtor = V.Validator()
r = vtor.check('integer(0, 9)', False)
print(type(r), repr(r), r is False)
print(repr(V.is_integer(False, '0', '9')))

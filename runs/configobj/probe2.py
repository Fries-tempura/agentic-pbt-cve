from configobj import ConfigObj
from configobj.validate import Validator

v = Validator()

print("--- nan ---")
print(repr(v.check('float(0, 1)', 'nan')))
print(repr(v.check('float(min=0, max=1)', float('nan'))))
print(repr(v.check('float(0, 1)', '-nan')))

print("--- shared default ---")
v2 = Validator()
a = v2.check('pass(default=list(1, 2))', None, missing=True)
a.append('3')
b = v2.check('pass(default=list(1, 2))', None, missing=True)
print(a, b, a is b)

print("--- configobj end-to-end shared default ---")
spec = """
[__many__]
items = pass(default=list('a', 'b'))
""".splitlines()
conf = ConfigObj({'s1': {}, 's2': {}}, configspec=spec)
conf.validate(Validator())
print(conf['s1']['items'] is conf['s2']['items'])
conf['s1']['items'].append('zzz')
print(conf['s1']['items'], conf['s2']['items'])

print("--- arity TypeError via ConfigObj.validate ---")
conf2 = ConfigObj({'x': '5'}, configspec=['x = integer(1, 2, 3)'])
try:
    conf2.validate(Validator())
except Exception as e:
    print('EXC', type(e).__name__, e)

conf3 = ConfigObj({'x': '5'}, configspec=['x = integer(bogus=1)'])
try:
    conf3.validate(Validator())
except Exception as e:
    print('EXC', type(e).__name__, e)

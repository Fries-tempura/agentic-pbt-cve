from configobj.validate import *

v = Validator()

print("bool:", repr(v.check('integer(0, 9)', False)))

for n in [0, 1, 16777218, 4294967295]:
    s = numToDottedQuad(n)
    print(n, s, dottedQuadToNum(s))

try:
    print(v.check('integer(1,2,3)', '5'))
except Exception as e:
    print('EXC', type(e).__name__, e)

a = v.get_default_value('pass(default=list(1, 2, 3))')
b = v.get_default_value('pass(default=list(1, 2, 3))')
print("shared default list:", a is b)

print(repr(v.check('ip_addr', '1 ')))
print(repr(v.check('ip_addr', '0x1.2.3.4')))

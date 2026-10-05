from configobj.validate import Validator

v = Validator()
check = "pass(default=list('a', 'b'))"

first = v.get_default_value(check)
first.append('MUTATED')
second = v.get_default_value(check)

print(second)
assert second == ['a', 'b'], second

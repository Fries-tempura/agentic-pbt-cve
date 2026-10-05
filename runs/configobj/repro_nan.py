from configobj.validate import Validator

v = Validator()
assert v.check('float(0, 1)', 'nan') != v.check('float(0, 1)', 'nan')  # nan accepted
print("float(0, 1) accepted:", v.check('float(0, 1)', 'nan'))

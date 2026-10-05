import doctest
from configobj import validate as V

globs = dict(V.__dict__)
globs['vtor'] = V.Validator()
runner = doctest.DocTestRunner(
    optionflags=doctest.IGNORE_EXCEPTION_DETAIL | doctest.ELLIPSIS)
for t in doctest.DocTestFinder().find(V.is_integer, globs=globs):
    runner.run(t)
print(runner.summarize())

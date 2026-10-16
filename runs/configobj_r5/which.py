import time
from configobj.validate import Validator
V = Validator
arg = "default=list(" + "a , "*12 + ")"
for name in ['_list_arg','_paramfinder','_matchfinder']:
    rx = getattr(V, name)
    t=time.perf_counter()
    rx.match(arg)
    print(name, round(time.perf_counter()-t,3))

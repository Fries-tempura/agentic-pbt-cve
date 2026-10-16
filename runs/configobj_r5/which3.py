import time
from configobj.validate import Validator
V = Validator
# exact arg_string from _func_re on "string_list(default=list(a , a , ...)":
argstr = "default=list(" + "a , "*12   # NOTE: list( is UNCLOSED (last ) stripped by _func_re)
for n in [10,12,13]:
    a = "default=list(" + "a , "*n
    t=time.perf_counter(); V._matchfinder.match(a); print("matchfinder n=",n, round(time.perf_counter()-t,3))

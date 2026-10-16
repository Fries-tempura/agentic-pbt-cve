import time
from configobj.validate import Validator
v = Validator()
for n in [10, 12, 14, 16]:
    s = "string_list(default=list(" + "a , "*n + ")"
    t = time.perf_counter()
    try: v.check(s, "x")
    except Exception: pass
    print(n, round(time.perf_counter()-t, 3))

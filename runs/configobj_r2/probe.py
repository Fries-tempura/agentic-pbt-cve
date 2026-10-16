import time
from configobj.validate import Validator
cands = {
 "open_parens": lambda n: "(" * n,
 "a_open": lambda n: "a(" * n,
 "spaces_arg": lambda n: "f(" + "a" + " " * n + "=",
 "commas": lambda n: "f(" + "a " * n + "=",
 "unquoted_eq": lambda n: "f(" + "a" * n + "=)",
 "kw_spaces": lambda n: "f(x=" + " a" * n + "=)",
 "list_arg": lambda n: "f(x=list(" + "a " * n + "=))",
}
for name, g in cands.items():
    for n in (1000, 2000, 4000):
        t = time.perf_counter()
        try: Validator().check(g(n), "x")
        except Exception as e: pass
        print(name, n, round(time.perf_counter() - t, 3))

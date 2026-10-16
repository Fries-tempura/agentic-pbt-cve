import time
from configobj.validate import Validator
v = Validator()
tests = {
  "closed, spaces-before-comma": "string_list(default=list(" + "'a' , "*14 + "'z'))",
  "unterminated list paren":     "string_list(default=list(" + "a , "*14 + ")",
  "plain many args spaces":      "string_list(" + "a , "*16 + "z)",
}
for name, s in tests.items():
    t=time.perf_counter()
    try: v.check(s,"x")
    except Exception as e: pass
    print(name, round(time.perf_counter()-t,3))

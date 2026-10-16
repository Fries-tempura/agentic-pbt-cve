import time, re
from configobj.validate import Validator
V = Validator
for n in (8000, 16000):
    s = "a" * n + "="
    for name, rx in (("_matchfinder", V._matchfinder), ("_paramfinder.findall", V._paramfinder)):
        t = time.perf_counter()
        (rx.match(s) if name == "_matchfinder" else rx.findall(s))
        print(name, n, round(time.perf_counter() - t, 2))
    t = time.perf_counter()
    try: V().check("integer(" + s + ")", "1")
    except Exception as e: print(type(e).__name__)
    print("check", n, round(time.perf_counter() - t, 2))

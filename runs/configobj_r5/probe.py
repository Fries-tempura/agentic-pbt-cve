import time
from configobj.validate import Validator
v = Validator({'cap': lambda value,*a,**k:(a,k)})
for pat in ['a ', 'a', ' a', 'a=a ', "a'", 'a,', '"a', 'a=']:
    for n in [10, 15, 20, 25]:
        s = 'cap(' + pat*n + ',=)'
        t=time.perf_counter()
        try: v.check(s,'x')
        except Exception as e: pass
        print(repr(pat), n, round(time.perf_counter()-t,4))

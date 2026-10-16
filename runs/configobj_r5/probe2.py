import time
from configobj.validate import Validator
v = Validator({'cap': lambda value,*a,**k:(a,k)})
def T(s):
    t=time.perf_counter()
    try: v._parse_check(s)
    except Exception: pass
    return time.perf_counter()-t
for pre in ['a=list(', 'a=list(x', 'a=list(x,']:
  for pat in ['x ', ' x', 'x , ', 'x,', ' ', 'x=', "'"]:
    for n in [6, 9, 12]:
        s = 'cap(' + pre + pat*n + ')(' 
        print(flush=True,*[repr(pre), repr(pat), n, round(T(s),4)])

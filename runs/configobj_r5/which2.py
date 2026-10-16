import time
from configobj.validate import Validator
V = Validator
argstr = "default=list(" + "a , "*12 + ")"
t=time.perf_counter(); V._matchfinder.match(argstr); print("matchfinder.match", round(time.perf_counter()-t,3))
t=time.perf_counter(); V._paramfinder.findall(argstr); print("paramfinder.findall", round(time.perf_counter()-t,3))
# the list body alone against _list_members
body = "a , "*12
t=time.perf_counter(); V._list_members.findall(body); print("list_members.findall", round(time.perf_counter()-t,3))

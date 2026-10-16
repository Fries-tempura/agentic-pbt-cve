import time
from dparse import parse, filetypes
for n in range(8, 21, 2):
    content = "-i https://" + "a.1" * n + "\nrequests==2.0"
    t = time.perf_counter()
    parse(content, file_type=filetypes.requirements_txt)
    print(n, round(time.perf_counter() - t, 3), flush=True)

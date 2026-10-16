import time
from dparse import parse, filetypes

content = "--index-url " + "https://" * 1000 + "\nrequests==2.0\n"
t = time.perf_counter()
parse(content, file_type=filetypes.requirements_txt)
print(f"{len(content)} bytes parsed in {time.perf_counter() - t:.1f}s")

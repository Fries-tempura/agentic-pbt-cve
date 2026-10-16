import time
from dparse import parse, filetypes

for n in (200, 400, 800):
    content = "--index-url " + "https://" * n + "\nrequests==2.0\n"
    t = time.time()
    parse(content, file_type=filetypes.requirements_txt)
    print(n, len(content), f"{time.time() - t:.2f}s")

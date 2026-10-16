import re
import time


def fixed(line):
    groups = re.split(r"[=\s]+", line.strip(), maxsplit=2)
    if len(groups) >= 2:
        return groups[1] if groups[1].endswith("/") else groups[1] + "/"
    return None


cases = {
    "--index-url https://some.foo/": "https://some.foo/",
    "-i https://some.foo/": "https://some.foo/",
    "--extra-index-url https://some.foo": "https://some.foo/",
    "--extra-index-url https://some.foo # some lousy comment": "https://some.foo/",
    "-i\t\t https://some.foo \t\t    # some lousy comment": "https://some.foo/",
    "--index-url": None,
    "--index-url=https://some.foo/": "https://some.foo/",
    "-i=https://some.foo/": "https://some.foo/",
    "--extra-index-url=https://some.foo": "https://some.foo/",
    "--extra-index-url=https://some.foo # some lousy comment": "https://some.foo/",
    "-i\t\t =https://some.foo \t\t    # some lousy comment": "https://some.foo/",
    "-i http://10.0.0.5:8080/simple/": "http://10.0.0.5:8080/simple/",
}
for k, v in cases.items():
    assert fixed(k) == v, (k, fixed(k))
t = time.perf_counter()
fixed("-i " + "https://" * 100000)
print("all cases ok; 800KB payload in", round(time.perf_counter() - t, 4), "s")

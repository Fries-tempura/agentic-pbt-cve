import time, sys
from setuptools.package_index import find_external_links, htmldecode
pages = {"lt_a_spaces": lambda n: "<a" + " "*n, "lt_a_rel_spaces": lambda n: "<a rel"+" "*n,
         "rel_rep": lambda n: "<"+"a rel=x "*(n//8), "href_rep": lambda n: "href="*(n//5),
         "amp": lambda n: "&"+"a"*n, "lt": lambda n: "<"*n, "lt_rel": lambda n: "< rel="*(n//6)}
for k, f in pages.items():
    for n in (1000, 2000, 4000):
        p = f(n); t = time.perf_counter(); list(find_external_links("https://h/", p)); a = time.perf_counter()-t
        t = time.perf_counter(); htmldecode(p); b = time.perf_counter()-t
        print(f"{k:16} n={n:5} fel={a:.3f}s htmldecode={b:.4f}s", flush=True)

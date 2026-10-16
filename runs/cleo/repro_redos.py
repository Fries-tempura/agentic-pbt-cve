import re, time
P = r"^<(\w+|(\w+=[\w,]+;?)*)>.+</(\w+|(\w+=\w+;?)*)?>$"
for n in range(4, 11):
    s = "<a=" + "bbbbbb=" * n
    t = time.perf_counter(); re.match(P, s); print(n, len(s), round(time.perf_counter() - t, 3))

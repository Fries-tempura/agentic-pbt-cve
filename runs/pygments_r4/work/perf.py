import time, itertools
from pygments.lexers.archetype import OdinLexer, CadlLexer, AdlLexer
units = list("aP1T.-:|[]{}()\"' \t\n/^\\x") + ["a.", "a-", "1.", "a1", "aa::", "-aa", ".a", "P1", "T1", "[a", "{/", "{^", "a-a", " -", "(\n"]
res=[]
for L in (OdinLexer, CadlLexer, AdlLexer):
  for pre in ["", "(", "[", "{", "|", "/", "\"", "P", "definition\n ", "language\n "]:
    for a,b in itertools.product(units, repeat=2):
        s = pre + (a+b)*1500
        t=time.perf_counter(); list(L().get_tokens(s)); d=time.perf_counter()-t
        if d>0.5: res.append((d,L.__name__,pre,a,b))
for r in sorted(res,reverse=True)[:20]: print(r)

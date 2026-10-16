import time
from pygments.lexers.archetype import OdinLexer, CadlLexer, AdlLexer
for L in (AdlLexer, CadlLexer, OdinLexer):
  for name, f in [("spaces", lambda n:" "*n+"x"), ("aid", lambda n:"a"*n), ("aid-dot", lambda n:"aa."*n), ("dash", lambda n:"aa-"*n),("hex",lambda n:"("+"1-"*n), ("meta", lambda n:"("+"a"*n+"!"),("P", lambda n:"P"+"1"*n), ("termcode", lambda n:"[a("+"x"*n), ("pipe", lambda n:"|"*1+"1"*n)]:
    for n in (2000, 4000, 8000):
        s=f(n); t=time.perf_counter(); list(L().get_tokens(s)); print(L.__name__, name, n, round(time.perf_counter()-t,3))

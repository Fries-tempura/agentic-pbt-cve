import time
from pygments.lexers.archetype import *
def t(lx, s):
    t0=time.perf_counter(); list(lx().get_tokens(s)); return time.perf_counter()-t0
for n in (250,500,1000):
    print(n, 'adl archid', t(AdlLexer, 'aa-aa-aa.'+'a'*n))
    print(n, 'adl archid dash', t(AdlLexer, 'aa-aa-aa.a'+'-'*n))
    print(n, 'cadl anycode', t(CadlLexer, '[aa-aa-aa.'+'a'*n))
    print(n, 'adl tabs', t(AdlLexer, '\t'*n))

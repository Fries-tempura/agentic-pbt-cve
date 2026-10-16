import time
from pygments.lexers.archetype import *
cases = {
 'adl ws': (AdlLexer, ' '),
 'adl metadata guid': (AdlLexer, None),
 'archid': (OdinLexer, 'a'),
}
def t(lx, s):
    t0=time.perf_counter(); list(lx().get_tokens(s)); return time.perf_counter()-t0
for n in (1000,2000,4000):
    print(n, 'adl spaces', t(AdlLexer, ' '*n+'x'))
    print(n, 'adl metadata', t(AdlLexer, '('+'a-'*n))
    print(n, 'archid', t(OdinLexer, 'aa-aa-aa.'+'a'*n))
    print(n, 'cadl tabs', t(CadlLexer, '\t'*n+'x'))
    print(n, 'odin ws', t(OdinLexer, ' \t'*n+'x'))
    print(n, 'adl metadata digits', t(AdlLexer, '(' + '1'*n + 'g'))

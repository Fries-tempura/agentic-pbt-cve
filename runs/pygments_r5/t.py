import time
from pygments.lexers.archetype import AdlLexer, CadlLexer, OdinLexer
def t(L, s):
    t0=time.time(); toks=list(L().get_tokens_unprocessed(s)); return time.time()-t0, ''.join(v for _,_,v in toks)==s
for n in [1000,2000,4000]:
    print(n,
      'adl-word', t(AdlLexer,'a'*n),
      'adl-sp', t(AdlLexer,' '*n+'x'),
      'adl-odinlines', t(AdlLexer,'language\n'+'x\n'*n),
      'cadl-{/', t(CadlLexer,'{/'*n),
      'odin-str', t(OdinLexer,'P'+'1'*n),
      'cadl-anycode', t(CadlLexer,'['+'a'*n),
      'cadl-type', t(CadlLexer,'Ab<Ab'+'<'*n),
      'adl-guid', t(AdlLexer,'archetype ('+'a-'*n),
    )

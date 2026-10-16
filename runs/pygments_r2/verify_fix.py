import time
from pygments.lexer import inherit
from pygments.token import Whitespace
from pygments.lexers.archetype import AdlLexer, CadlLexer
class FixedAdl(AdlLexer):
    tokens = {'root': [inherit, (r'[ \t]+', Whitespace)]}
class FixedCadl(CadlLexer):
    tokens = {'any_code': [inherit, (r'\s+', Whitespace)]}
def t(lx, s):
    t0=time.perf_counter(); list(lx().get_tokens(s)); return time.perf_counter()-t0
for n in (4000,16000,64000):
    print(n, t(FixedAdl, ' '*n+'x'), t(FixedCadl, '['+' '*n+'x'))
import glob
for f in glob.glob('/Users/auderyliu/Documents/NTU/project/agentic-pbt-main/dataset/checkouts/CVE-2026-4539__pygments/tests/examplefiles/*/*.adl*')+glob.glob('/Users/auderyliu/Documents/NTU/project/agentic-pbt-main/dataset/checkouts/CVE-2026-4539__pygments/tests/examplefiles/cadl/*'):
    s=open(f).read()
    if f.endswith('.output'): continue
    a=list(AdlLexer().get_tokens(s)); b=list(FixedAdl().get_tokens(s))
    print(f.split('/')[-1], ''.join(v for _,v in a)==''.join(v for _,v in b), sum(1 for tk,_ in a if 'Error' in str(tk)), sum(1 for tk,_ in b if 'Error' in str(tk)))

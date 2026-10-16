import time
from pygments.lexers.archetype import AdlLexer
from pygments.token import Whitespace, Text
class Fixed(AdlLexer):
    tokens = {'root': AdlLexer.tokens['root'] + [(r'[ \t]+', Whitespace), (r'\w+', Text)]}
for s in [" "*16000+"!", "a"*16000+"!", "aa."*6000]:
    t=time.perf_counter(); list(Fixed().get_tokens(s)); print(round(time.perf_counter()-t,3))

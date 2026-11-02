import time, re
import soupsieve as sv
from soupsieve import css_parser as cp
from soupsieve.util import SelectorSyntaxError

orig = cp.CSSParser.selector_iter

def fixed_iter(self, pattern):
    m = cp.RE_WS_BEGIN.search(pattern)
    index = m.end(0) if m else 0
    while index < len(pattern) and not cp.RE_WS_END.match(pattern, index):
        m = None
        for v in self.CSS_TOKENS:
            m = v.match(pattern, index, self.flags)
            if m:
                index = m.end(0)
                yield v.get_name(), m
                break
        if m is None:
            raise SelectorSyntaxError(f"Invalid character {pattern[index]!r} position {index}", self.pattern, index)

samples = ['a b', ' a > b ', 'a /* c */ ', ':is(a, b) ', 'a,b', 'a\n', '/**/a/**/', 'div:not(.x) > p ~ i + b',
           'a ' + ' ' * 50, '[x = "y" i ] ', ':nth-child(2n + 1 of a ) ']
for s in samples:
    a = cp.CSSParser(s).parse_selectors(orig(cp.CSSParser(s), s))
    b = cp.CSSParser(s).parse_selectors(fixed_iter(cp.CSSParser(s), s))
    assert a == b, s
cp.CSSParser.selector_iter = fixed_iter
for n in (8000, 16000):
    cp._purge_cache(); t = time.perf_counter(); sv.compile('a' + ' ' * n + 'b'); print(n, round(time.perf_counter() - t, 4))

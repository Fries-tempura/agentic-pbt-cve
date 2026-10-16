import copy
from pygments.lexer import bygroups
from pygments.token import Name, Whitespace, Error
from pygments.lexers.archetype import AdlLexer

ARCH_ID = (r'([ \t]*)(([a-zA-Z]\w+(\.[a-zA-Z]\w+)*::)?[a-zA-Z]\w+(-[a-zA-Z]\w+){2}'
           r'\.\w[\w-]*\.v\d+(\.\d+){,2}((-[a-z]+)(\.\d+)?)?)')


class PatchedAdl(AdlLexer):
    tokens = {
        'archetype_id': [(ARCH_ID, bygroups(Whitespace, Name.Decorator))],
    }
    tokens['root'] = copy.copy(AdlLexer.tokens['root']) + [
        (r'[a-zA-Z]\w*', Error),
        (r'[ \t]+', Whitespace),
    ]

import re, lxml_html_clean.clean as _  # noqa
import sys; m = sys.modules['lxml_html_clean.clean']
_css_escape_re = re.compile(r'\\(?:([0-9a-fA-F]{1,6})[ \t\r\n\f]?|(.))', re.S)
def dec(s):
    def repl(mm):
        if mm.group(1):
            cp = int(mm.group(1), 16)
            return chr(cp) if 0 < cp <= 0x10FFFF and not 0xD800 <= cp <= 0xDFFF else '�'
        return mm.group(2)
    return _css_escape_re.sub(repl, s)
orig = m.Cleaner._has_sneaky_javascript
m.Cleaner._has_sneaky_javascript = lambda self, s: orig(self, dec(self._substitute_comments('', s)))
import pytest; sys.exit(pytest.main(['-q', 'test_clean.py']))

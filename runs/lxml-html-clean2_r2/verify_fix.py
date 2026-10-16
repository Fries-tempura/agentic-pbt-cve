import re
from lxml_html_clean import Cleaner
Cleaner._css_unicode_escape_re = re.compile(r'\\(?:([0-9a-fA-F]{1,6})\s?|([^\n\r\f0-9a-fA-F]))')
def _dec(self, style):
    def rep(m):
        if m.group(1) is None:
            return m.group(2)
        try: return chr(int(m.group(1), 16))
        except (ValueError, OverflowError): return m.group(0)
    return self._css_unicode_escape_re.sub(rep, style)
Cleaner._decode_css_unicode_escapes = _dec
import test_clean_pbt as t
t.test_style_tag_has_no_dangerous_css(); t.test_inline_style_has_no_dangerous_css(); print("fixed: tests pass")

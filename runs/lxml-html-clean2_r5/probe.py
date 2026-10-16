import warnings; warnings.simplefilter('ignore')
from lxml_html_clean import Cleaner
c = Cleaner(host_whitelist=['good.com'])
for u in ['https://good.com/x', 'https://evil.com\\@good.com/', 'https://good.com\\@evil.com/', 'https://evil.com/\\good.com',
          'https:\\\\evil.com/', 'https:/\\evil.com/', 'HTTPS://good.com', ' https://evil.com', 'https://evil.com%2f@good.com',
          'https://evil.com&#9;@good.com', 'https://good.com:443@evil.com', 'https:///evil.com', 'https:////evil.com', 'https://good.com\x00.evil.com']:
    print(repr(u), '->', c.clean_html('<div><iframe src="%s"></iframe></div>' % u))
# css escapes
d = Cleaner(style=False, inline_style=False)
for s in ['x{background:url(\\6a avascript:alert(1))}', 'x{width:ex\\pression(alert(1))}', '/* <\\69mg src=x onerror=alert(1)> */', 'x{a:b}/*<a*/']:
    print(repr(s), '->', d.clean_html('<div><style>%s</style></div>' % s))

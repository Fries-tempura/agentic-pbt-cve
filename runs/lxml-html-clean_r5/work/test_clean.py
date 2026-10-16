import re
from hypothesis import given, settings, strategies as st, HealthCheck
from lxml import etree
from lxml.html import fromstring, tostring
from lxml_html_clean import clean, Cleaner, clean_html

def css_unescape(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    def rep(m):
        h = m.group(1)
        if h:
            try: return chr(int(h, 16))
            except (ValueError, OverflowError): return ''
        return m.group(2)
    s = re.sub(r'\\(?:([0-9a-fA-F]{1,6})\s?|(.))', rep, s, flags=re.S)
    return re.sub(r'\s+', '', s).lower()

kw = st.sampled_from(['@import', 'expression(', 'javascript:'])

def obfuscate(word):
    # mix of real CSS obfuscation techniques
    chars = []
    for c in word:
        chars.append(st.sampled_from([c, c.upper(), '\\' + format(ord(c), 'x') + ' ',
                                      '\\' + format(ord(c), '06x'), '\\' + c, c + '/**/']))
    return st.tuples(*chars).map(''.join)

obf = kw.flatmap(obfuscate)
filler = st.sampled_from(['', 'color:red;', 'a{', '}', ' ', 'url(', '"', "'", 'alert(1)', ')'])
css = st.tuples(filler, obf, filler, st.sampled_from(['url(http://evil/x.css)', '"http://evil/x"', 'alert(1)', 'alert(1))'])).map(''.join)

BAD = ('@import', 'expression(', 'javascript:')

@settings(max_examples=2000, suppress_health_check=list(HealthCheck))
@given(css)
def test_style_tag_safe(c):
    doc = fromstring('<div><style>%s</style><p>x</p></div>' % c.replace('<', ''))
    clean(doc)
    for el in doc.iter('style'):
        t = css_unescape(el.text or '')
        assert not any(b in t for b in BAD), (c, el.text)

@settings(max_examples=2000, suppress_health_check=list(HealthCheck))
@given(css)
def test_style_attr_safe(c):
    doc = fromstring('<div><p>x</p></div>')
    doc[0].set('style', c)
    clean(doc)
    for el in doc.iter():
        s = el.get('style')
        if s:
            t = css_unescape(s)
            assert not any(b in t for b in BAD), (c, s)

scheme_obf = st.tuples(*[st.sampled_from([c, c.upper(), '\t', '\n']).map(lambda x, c=c: x if x in (c, c.upper()) else c + x) for c in 'javascript']).map(''.join)
@settings(max_examples=1000)
@given(scheme_obf, st.sampled_from(['a', 'iframe', 'img', 'form', 'area', 'base']), st.sampled_from(['href', 'src', 'action', 'formaction', 'background']))
def test_no_js_links(s, tag, attr):
    doc = fromstring('<div><%s %s="%s:alert(1)">x</%s></div>' % (tag, attr, s, tag))
    clean(doc)
    out = tostring(doc, encoding=str)
    for el in doc.iter():
        for v in el.attrib.values():
            assert 'javascript:' not in re.sub(r'[\s\x00-\x1f]', '', v).lower(), out

@settings(max_examples=500)
@given(st.text(alphabet='<>/="\' abcdefghijklmnopqrstuvwxyzonclickscriptstyle:;()', min_size=1))
def test_no_crash_no_script(s):
    try:
        out = clean_html('<div>' + s + '</div>')
    except etree.ParserError:
        return
    doc = fromstring(out)
    assert not list(doc.iter('script'))
    for el in doc.iter(etree.Element):
        assert not any(a.startswith('on') for a in el.attrib), out

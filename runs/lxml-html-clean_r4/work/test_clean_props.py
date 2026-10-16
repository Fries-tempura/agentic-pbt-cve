import re
from hypothesis import given, settings, strategies as st, HealthCheck
from lxml import html as lhtml
from lxml_html_clean import Cleaner, clean_html

def css_escape(ch, style):
    h = format(ord(ch), 'x')
    if style == 0: return ch
    if style == 1: return '\\' + h + ' '
    if style == 2: return '\\' + h.rjust(6, '0')
    return '\\' + ch  # identity escape

@st.composite
def obfuscated_import(draw):
    word = 'import'
    parts = [css_escape(c, draw(st.integers(0, 3))) for c in word]
    return '@' + ''.join(parts) + " url('http://evil.example/x.css');"

def css_unescape(s):
    s = re.sub(r'\\([0-9a-fA-F]{1,6}) ?', lambda m: chr(int(m.group(1), 16)), s)
    return re.sub(r'\\(.)', r'\1', s)

# Property: Cleaner(javascript=True) claims "The imported CSS can do anything; we just can't allow" @import.
@settings(max_examples=500)
@given(obfuscated_import(), st.sampled_from(['', 'p{color:red}', 'b{}']))
def test_no_import_in_style_tag(imp, other):
    out = clean_html(f'<div><style>{other}{imp}</style><p>x</p></div>')
    for st_el in lhtml.fromstring(out).iter('style'):
        assert '@import' not in css_unescape(st_el.text or '').lower(), out

@settings(max_examples=500)
@given(obfuscated_import())
def test_no_import_in_style_attr(imp):
    out = clean_html(f'<div><p style="color:red;{imp}">x</p></div>')
    for el in lhtml.fromstring(out).iter():
        assert '@import' not in css_unescape(el.get('style') or '').lower(), out

# Property: javascript links removed
@settings(max_examples=500)
@given(st.lists(st.sampled_from(['j','a','v','a','s','c','r','i','p','t']), min_size=0, max_size=0),
       st.sampled_from(['javascript', 'JaVaScRiPt', 'vbscript', 'jscript']),
       st.sampled_from(['', ' ', '\t', '\n', '%20', '&#9;', '&#x0A;', '&#106;']),
       st.sampled_from(['a', 'img', 'iframe', 'form', 'area']),
       st.sampled_from(['href', 'src', 'action']))
def test_no_js_links(_, scheme, ws, tag, attr):
    s = scheme[:3] + ws + scheme[3:]
    out = clean_html(f'<div><{tag} {attr}="{s}:alert(1)">x</{tag}></div>')
    doc = lhtml.fromstring(out)
    for el in doc.iter():
        for v in el.attrib.values():
            norm = re.sub(r'\s', '', v).lower()
            assert not re.match(r'(java|vb|j)script:', norm), out

# Property: idempotence of clean_html
html_frag = st.lists(st.sampled_from([
    '<p>', '</p>', '<b>', '</b>', '<style>', '</style>', 'a{b:c}', '<a href="http://x/">', '</a>',
    '<script>', '</script>', '<!-- c -->', '<form>', '<input>', '<iframe src="http://x">', '</iframe>',
    'text', '<html>', '<head>', '<title>t</title>', '<body>', '<div>', '</div>', '<img src="x">',
    '<noscript>', '</noscript>', '<math>', '</math>', '<svg>', '</svg>', '<textarea>', '</textarea>',
]), min_size=1).map(''.join)

@settings(max_examples=500, suppress_health_check=list(HealthCheck))
@given(html_frag)
def test_idempotent(s):
    try:
        once = clean_html(s)
    except Exception:
        return
    assert clean_html(once) == once

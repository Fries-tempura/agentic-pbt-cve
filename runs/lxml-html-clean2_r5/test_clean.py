import re
from hypothesis import given, settings, strategies as st, HealthCheck
from lxml import etree
import lxml.html
from lxml_html_clean import Cleaner, clean_html
from lxml_html_clean.clean import _has_javascript_scheme

TAGS = ['a', 'div', 'p', 'img', 'script', 'style', 'base', 'link', 'meta', 'iframe', 'embed',
        'object', 'form', 'input', 'svg', 'math', 'noscript', 'span', 'title', 'head', 'body',
        'image', 'frame', 'applet', 'param', 'blink', 'textarea', 'button', 'unknowntag']
ATTRS = ['href', 'src', 'style', 'onclick', 'onerror', 'class', 'action', 'rel', 'type', 'xlink:href', 'formaction', 'background']
SCHEMES = ['javascript:alert(1)', 'jav\tascript:alert(1)', 'JaVaScRiPt:x', ' javascript:x', 'vbscript:x',
           'data:text/html,<script>', 'data:image/svg+xml;base64,AAA', 'http://ok.com/', '#frag', 'java%0ascript:x',
           '&#106;avascript:x', 'expression(alert(1))', 'url(javascript:x)', 'x', 'javascript&colon;x']

text = st.lists(st.sampled_from(list('ab <>"\'=/:;()&#\\\t\n') + ['script', 'javascript:', 'expression(', '@import', '/*', '*/', 'on', 'error']), max_size=12).map("".join)
attrval = st.one_of(st.sampled_from(SCHEMES), text)

@st.composite
def element(draw, depth=0):
    tag = draw(st.sampled_from(TAGS))
    attrs = draw(st.lists(st.tuples(st.sampled_from(ATTRS), attrval), max_size=3, unique_by=lambda t: t[0]))
    a = ''.join(' %s="%s"' % (k, v.replace('"', '&quot;')) for k, v in attrs)
    inner = ''
    if depth < 3:
        inner = ''.join(draw(st.lists(st.one_of(text, element(depth + 1)), max_size=3)))
    return '<%s%s>%s</%s>' % (tag, a, inner, tag)

html_docs = st.lists(st.one_of(element(), text), min_size=1, max_size=4).map(''.join)

def check_safe(out):
    doc = lxml.html.fromstring(out) if out.strip() else None
    if doc is None:
        return
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        assert el.tag not in ('script', 'iframe', 'embed', 'object', 'applet', 'frame', 'link', 'meta', 'form', 'input'), (el.tag, out)
        for k, v in el.attrib.items():
            assert not k.lower().startswith('on'), (k, out)
            if k in ('href', 'src', 'action'):
                norm = re.sub(r'[\s\x00-\x20]', '', v).lower()
                assert not norm.startswith(('javascript:', 'vbscript:', 'data:text')), (k, v, out)
            if k == 'style':
                assert 'expression(' not in re.sub(r'\s', '', v).lower(), (v, out)

@settings(max_examples=2000, suppress_health_check=list(HealthCheck), deadline=None)
@given(html_docs)
def test_default_clean_is_safe(html):
    try:
        out = clean_html(html)
    except (etree.ParserError, ValueError, AssertionError):
        return
    check_safe(out)

@settings(max_examples=2000, suppress_health_check=list(HealthCheck), deadline=None)
@given(html_docs)
def test_safe_attrs_off_still_strips_js(html):
    c = Cleaner(safe_attrs_only=False)
    try:
        out = c.clean_html(html)
    except (etree.ParserError, ValueError, AssertionError):
        return
    check_safe(out)

@settings(max_examples=2000, suppress_health_check=list(HealthCheck), deadline=None)
@given(html_docs)
def test_style_kept_no_js(html):
    c = Cleaner(style=False, inline_style=False, safe_attrs_only=False)
    try:
        out = c.clean_html(html)
    except (etree.ParserError, ValueError, AssertionError):
        return
    check_safe(out)
    doc = lxml.html.fromstring(out) if out.strip() else None
    if doc is None: return
    for el in doc.iter('style'):
        t = re.sub(r'\s', '', (el.text or '')).lower()
        assert 'expression(' not in t and '@import' not in t and 'javascript:' not in t, out

@settings(max_examples=1000, suppress_health_check=list(HealthCheck), deadline=None)
@given(html_docs)
def test_idempotent(html):
    try:
        once = clean_html(html)
    except (etree.ParserError, ValueError, AssertionError):
        return
    if not once.strip():
        return
    assert clean_html(once) == once

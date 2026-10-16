import re
from urllib.parse import unquote_plus
import lxml.html
from lxml import etree
from hypothesis import given, settings, strategies as st, HealthCheck
from lxml_html_clean import clean, clean_html
from lxml_html_clean.clean import _substitute_whitespace

TAGS = ["div", "p", "a", "img", "script", "style", "iframe", "embed", "object", "form",
        "input", "svg", "math", "noscript", "title", "textarea", "meta", "link", "span",
        "blink", "frame", "frameset", "applet", "param", "image", "foo", "html", "body", "head",
        "template", "select", "option", "xmp", "noembed", "table"]
ATTRS = ["href", "src", "onclick", "style", "title", "action", "class", "onerror", "rel", "type",
         "background", "formaction", "xlink:href"]
SCHEMES = ["javascript:", "JaVaScRiPt:", "java\tscript:", "java&#x09;script:", " javascript:",
           "&#x6A;avascript:", "data:text/html,", "vbscript:", "http://x/", "#", "", "java%0ascript:",
           "data:image/svg+xml;base64,", "\x01javascript:", "&#1;javascript:", "&#x1f;javascript:",
           "javas&#x1A;cript:", "jav&#0;ascript:"]
PAYLOADS = ["alert(1)", "x", "expression(alert(1))", "url(javascript:alert(1))",
            "<img src=x onerror=alert(1)>", "</style><script>alert(1)</script>",
            "/* <a> */", "@import 'x';", "e\\xpression(1)", "</noscript><img src=x onerror=1>",
            "<!--", "-->", "]]>", "<![CDATA[", "<", ">", "\"", "'", "&lt;script&gt;"]

text = st.sampled_from(PAYLOADS) | st.text(alphabet='<>/="\' abc&;!-:\\()*\t\n\x00\x1f', max_size=10)

@st.composite
def attr(draw):
    name = draw(st.sampled_from(ATTRS))
    val = draw(st.sampled_from(SCHEMES)) + draw(text)
    q = draw(st.sampled_from(['"', "'"]))
    val = val.replace(q, '')
    return f' {name}={q}{val}{q}'

node = st.recursive(
    text,
    lambda children: st.builds(
        lambda t, attrs, kids, close: f"<{t}{''.join(attrs)}>{''.join(kids)}" + (f"</{t}>" if close else ""),
        st.sampled_from(TAGS), st.lists(attr(), max_size=3), st.lists(children, max_size=4), st.booleans()),
    max_leaves=12,
)
docs = st.lists(node | st.sampled_from(["<!-- c -->", "<?pi x?>", "<!--[if IE]><script>alert(1)</script><![endif]-->"]),
                min_size=1, max_size=5).map("".join)

def is_js(v):
    v = _substitute_whitespace('', unquote_plus(v)).lower()
    return bool(re.search(r'(javascript|vbscript|jscript|livescript|mocha):', v)) or v.startswith('data:text')

def check_safe(out):
    doc = lxml.html.fromstring(out) if out.strip() else None
    if doc is None:
        return
    for el in doc.iter():
        if el.tag is etree.Comment:
            raise AssertionError(f"comment survived: {out!r}")
        if not isinstance(el.tag, str):
            continue
        assert el.tag not in ("script", "iframe", "embed", "object", "applet", "frame", "frameset",
                              "meta", "link", "form", "input"), (el.tag, out)
        for k, v in el.attrib.items():
            assert not k.startswith("on"), (k, out)
            if k in ("href", "src", "action", "background", "formaction"):
                assert not is_js(v), (k, v, out)

def safe_clean(h):
    try:
        return clean_html(h)
    except etree.ParserError:
        return None

@settings(max_examples=3000, suppress_health_check=list(HealthCheck), deadline=None)
@given(docs)
def test_output_safe_after_reparse(h):
    out = safe_clean(h)
    if out is None:
        return
    check_safe(out)

@settings(max_examples=3000, suppress_health_check=list(HealthCheck), deadline=None)
@given(docs)
def test_idempotent(h):
    out = safe_clean(h)
    if out is None or not out.strip():
        return
    out2 = safe_clean(out)
    assert out2 == out, (h, out, out2)

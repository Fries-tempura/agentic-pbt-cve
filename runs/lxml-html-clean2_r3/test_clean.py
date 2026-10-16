import re
from urllib.parse import unquote
from hypothesis import given, settings, strategies as st, HealthCheck
import lxml.html
from lxml import etree
from lxml_html_clean import clean_html, Cleaner
from lxml_html_clean.clean import fromstring as _fs

TAGS = ["a", "div", "p", "img", "script", "style", "svg", "math", "noscript", "iframe",
        "embed", "object", "form", "button", "input", "base", "link", "meta", "title",
        "textarea", "template", "image", "frame", "table", "select", "option", "xmp",
        "noembed", "noframes", "plaintext", "body", "head", "html", "span", "area"]
ATTRS = ["href", "src", "onclick", "onerror", "style", "action", "formaction", "xlink:href",
         "background", "srcset", "data", "rel", "type", "title", "class", "content",
         "http-equiv", "poster", "cite", "longdesc", "usemap"]
JS = st.sampled_from(["javascript:alert(1)", "JaVaScRiPt:alert(1)", " javascript:alert(1)",
                      "java\tscript:alert(1)", "java&#x09;script:alert(1)", "&#106;avascript:alert(1)",
                      "javascript&colon;alert(1)", "vbscript:x", "data:text/html,<script>alert(1)</script>",
                      "data:image/svg+xml;base64,AA", "java%0ascript:1", "jav&#x0A;ascript:1",
                      "\x01javascript:1", "&#1;javascript:1", "&#x1f;javascript:1", "&#0;javascript:1",
                      "x", "http://ok/", "expression(alert(1))", "url(javascript:1)", "\\6a avascript:1",
                      "<img src=x onerror=alert(1)>", "</style><script>alert(1)</script>",
                      "@import 'x'", "</noscript><img src=x onerror=1>", "/*</style>*/"])
val = st.one_of(JS, st.text(alphabet="<>/\"'=&#;:\\ \t\nabcjsx()", max_size=15))

@st.composite
def attr(draw):
    return '%s="%s"' % (draw(st.sampled_from(ATTRS)), draw(val).replace('"', "&quot;"))

@st.composite
def node(draw, depth=0):
    kind = draw(st.integers(0, 4 if depth < 4 else 1))
    if kind == 0:
        return draw(val)
    if kind == 1:
        return "<!--%s-->" % draw(val)
    tag = draw(st.sampled_from(TAGS))
    attrs = " ".join(draw(st.lists(attr(), max_size=3)))
    kids = "".join(draw(st.lists(node(depth + 1), max_size=3)))
    close = draw(st.booleans())
    return "<%s %s>%s%s" % (tag, attrs, kids, "</%s>" % tag if close else "")

html_doc = st.lists(node(), min_size=1, max_size=4).map("".join)

WS = re.compile(r"[\x00-\x20]+")
def js_url(v):
    v = WS.sub("", v.strip("\x00- ")).lower()
    v2 = WS.sub("", unquote(v))
    return any(re.match(r"(javascript|vbscript):", x) for x in (v, v2)) or \
        re.match(r"data:(text/html|image/svg)", v2) is not None

def check(out):
    doc = _fs("<div>%s</div>" % out) if out.strip() else None
    if doc is None:
        return
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        assert el.tag.lower() != "script", out
        for k, v in el.attrib.items():
            assert not k.lower().startswith("on"), out
            if k in ("href", "src", "action", "formaction", "xlink:href", "background", "data"):
                assert not js_url(v), (k, v, out)
            if k == "style":
                s = v.lower().replace(" ", "")
                assert "expression(" not in s and "javascript:" not in s, out
        if el.tag == "style":
            t = (el.text or "").lower()
            assert "<script" not in t and "onerror" not in t and "javascript:" not in t, out

@settings(max_examples=3000, suppress_health_check=list(HealthCheck), deadline=None)
@given(html_doc)
def test_default_clean_removes_js(s):
    try:
        out = clean_html(s)
    except (etree.ParserError, AssertionError, ValueError):
        return
    check(out)

@settings(max_examples=2000, suppress_health_check=list(HealthCheck), deadline=None)
@given(html_doc)
def test_style_kept_clean_removes_js(s):
    c = Cleaner(safe_attrs_only=False, style=False, inline_style=False, links=False)
    try:
        out = c.clean_html(s)
    except (etree.ParserError, AssertionError, ValueError):
        return
    check(out)

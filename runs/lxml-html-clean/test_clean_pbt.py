import re
from urllib.parse import unquote_plus

import lxml.html
from lxml import etree
from hypothesis import given, settings, strategies as st, HealthCheck

from lxml_html_clean import clean_html, Cleaner

TAGS = ["div", "p", "span", "a", "img", "script", "style", "svg", "math", "noscript",
        "iframe", "embed", "object", "form", "input", "button", "meta", "link", "base",
        "title", "head", "body", "html", "textarea", "select", "applet", "frame", "frameset",
        "blink", "marquee", "table", "td", "template", "image", "area", "video", "source"]

ATTR_NAMES = ["href", "src", "action", "formaction", "onclick", "onerror", "style",
              "srcset", "background", "data", "xlink:href", "rel", "http-equiv", "content",
              "type", "class", "id", "cite", "longdesc", "poster", "usemap"]

URL_VALUES = st.sampled_from([
    "javascript:alert(1)", "JaVaScRiPt:alert(1)", "java\tscript:alert(1)",
    "jav&#x09;ascript:alert(1)", "java%09script:alert(1)", "vbscript:x", "data:text/html,<script>",
    "data:image/png;base64,AAAA", "data:image/svg+xml;base64,AAAA",
    "http://example.com/", "https://evil.com/x", "#frag", "/rel/path", " javascript:x",
    "\x01javascript:x", "javascript&colon;alert(1)", "&#106;avascript:alert(1)",
])
TEXT = st.sampled_from([
    "hello", "expression(alert(1))", "@import 'x';", "url(javascript:x)",
    "</noscript><img src=x onerror=alert(1)>", "<img src=x onerror=alert(1)>",
    "/* <img src=x onerror=alert(1)> */", "a{color:red}", "</style><script>alert(1)</script>",
    "<!--", "-->", "]]>", "&lt;script&gt;",
])


@st.composite
def html_doc(draw, depth=0):
    tag = draw(st.sampled_from(TAGS))
    attrs = draw(st.dictionaries(st.sampled_from(ATTR_NAMES),
                                 st.one_of(URL_VALUES, TEXT), max_size=3))
    attr_s = "".join(f' {k}="{v.replace(chr(34), "&quot;")}"' for k, v in attrs.items())
    children = []
    if depth < 3:
        children = draw(st.lists(st.one_of(TEXT, html_doc(depth=depth + 1)), max_size=3))
    return f"<{tag}{attr_s}>{''.join(children)}</{tag}>"


DANGEROUS_TAGS = {"script", "iframe", "embed", "object", "applet", "frame", "frameset",
                  "meta", "link", "form", "input", "button", "textarea", "select",
                  "blink", "marquee"}


def _is_js_url(v):
    v = re.sub(r"[\s\x00-\x20]+", "", unquote_plus(v)).lower()
    return bool(re.match(r"(javascript|vbscript|jscript|livescript|mocha):", v)) or \
        v.startswith("data:text") or v.startswith("data:image/svg")


def check_output(out):
    if not out.strip():
        return
    doc = lxml.html.fromstring(out)
    for el in doc.iter():
        if not isinstance(el.tag, str):
            assert el.tag is not etree.Comment, out
            continue
        assert el.tag not in DANGEROUS_TAGS, (el.tag, out)
        for k, v in el.attrib.items():
            assert not k.lower().startswith("on"), (k, out)
            if k in lxml.html.defs.link_attrs:
                assert not _is_js_url(v), (k, v, out)
        if el.tag == "style":
            css = re.sub(r"\s", "", (el.text or "")).lower()
            assert "expression(" not in css, out
            assert "@import" not in css, out
            assert "javascript:" not in css, out


WRAPPED = st.lists(html_doc(), min_size=1, max_size=3).map(lambda xs: "<div>" + "".join(xs) + "</div>")


@settings(max_examples=3000, suppress_health_check=list(HealthCheck), deadline=None)
@given(WRAPPED)
def test_wrapped_default_clean_removes_dangerous_content(html):
    check_output(clean_html(html))


@settings(max_examples=2000, suppress_health_check=list(HealthCheck), deadline=None)
@given(WRAPPED)
def test_wrapped_reclean(html):
    check_output(clean_html(clean_html(html)))


@settings(max_examples=2000, suppress_health_check=list(HealthCheck), deadline=None)
@given(WRAPPED)
def test_wrapped_no_safe_attrs_only(html):
    check_output(Cleaner(safe_attrs_only=False).clean_html(html))


@settings(max_examples=3000, suppress_health_check=list(HealthCheck), deadline=None)
@given(st.lists(html_doc(), min_size=1, max_size=3).map("".join))
def test_default_clean_removes_dangerous_content(html):
    out = clean_html(html)
    check_output(out)


@settings(max_examples=2000, suppress_health_check=list(HealthCheck), deadline=None)
@given(st.lists(html_doc(), min_size=1, max_size=3).map("".join))
def test_clean_output_stable_under_reclean(html):
    # Cleaning already-clean output should not reveal anything dangerous either
    out = clean_html(html)
    out2 = clean_html(out)
    check_output(out2)


@settings(max_examples=2000, suppress_health_check=list(HealthCheck), deadline=None)
@given(st.lists(html_doc(), min_size=1, max_size=3).map("".join))
def test_clean_without_safe_attrs_only(html):
    out = Cleaner(safe_attrs_only=False).clean_html(html)
    check_output(out)

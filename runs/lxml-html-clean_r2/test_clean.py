import re
import warnings

import lxml.html
from hypothesis import given, settings, strategies as st, HealthCheck

from lxml_html_clean import Cleaner, clean_html

warnings.simplefilter("ignore")

# ---------- Property 1: host_whitelist cleaning never crashes on arbitrary src ----------

url_chars = st.sampled_from(list("abcdefghijklmnopqrstuvwxyz0123456789.:/?#@[]\\%-_ \t"))
host_like = st.text(url_chars, max_size=25)


@given(st.sampled_from(["http://", "https://", "//", "https:", ""]), host_like)
@settings(max_examples=1000)
def test_whitelist_clean_never_crashes(prefix, rest):
    cleaner = Cleaner(host_whitelist=["trusted.com"])
    url = prefix + rest
    html = '<div><iframe src="%s"></iframe></div>' % url.replace('"', "")
    cleaner.clean_html(html)  # must not raise


# ---------- Property 2: whitelisted embed only when browser host is whitelisted ----------

def browser_host(url):
    """Very small WHATWG-ish host extractor for special schemes (http/https)."""
    url = url.strip("\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f "
                    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f")
    url = re.sub(r"[\t\n\r]", "", url)
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):(.*)$", url, re.S)
    if not m or m.group(1).lower() not in ("http", "https"):
        return None
    rest = m.group(2).lstrip("/\\")
    authority = re.split(r"[/\\?#]", rest, maxsplit=1)[0]
    host = authority.rsplit("@", 1)[-1]
    if host.startswith("["):
        return host.split("]")[0] + "]"
    return host.split(":")[0].lower()


@given(
    st.sampled_from(["http", "https", "HTTPS"]),
    st.sampled_from(["//", "/\\", "\\\\", "///", "//"]),
    st.lists(st.sampled_from(["trusted.com", "evil.com", "@", "\\", "/", ":", "#", "?", "%2f", "a"]),
             min_size=1, max_size=6).map("".join),
)
@settings(max_examples=1000)
def test_whitelist_matches_browser_host(scheme, slashes, rest):
    url = scheme + ":" + slashes + rest
    cleaner = Cleaner(host_whitelist=["trusted.com"])
    el = lxml.html.fromstring('<iframe src="x"></iframe>')
    try:
        allowed = cleaner.allow_embedded_url(el, url)
    except ValueError:
        return
    if allowed:
        assert browser_host(url) == "trusted.com", url


# ---------- Property 3: default cleaner removes scripts / event handlers / js links ----------

tags = st.sampled_from(["a", "div", "img", "iframe", "svg", "math", "style", "noscript",
                        "script", "image", "object", "embed", "form", "p", "span", "table",
                        "template", "textarea", "title", "base", "link", "meta", "xmp", "frame"])
attrs = st.sampled_from(["href", "src", "onclick", "onerror", "style", "action", "background",
                         "data", "xlink:href", "formaction", "title", "type", "rel", "srcdoc"])
values = st.sampled_from(["javascript:alert(1)", " java\tscript:alert(1)", "JaVaScRiPt:x",
                          "data:text/html,<script>", "data:image/svg+xml;base64,AA",
                          "data:image/png;base64,AA", "&#106;avascript:x", "vbscript:x",
                          "http://x.com/", "x", "</style><img src=x onerror=alert(1)>",
                          "expression(alert(1))", "url(javascript:x)", "<script>alert(1)</script>"])


@st.composite
def html_docs(draw, depth=0):
    tag = draw(tags)
    a = draw(st.lists(st.tuples(attrs, values), max_size=3))
    attr_s = "".join(' %s="%s"' % (k, v.replace('"', "")) for k, v in a)
    children = ""
    if depth < 3:
        children = "".join(draw(st.lists(html_docs(depth=depth + 1), max_size=3)))
    text = draw(st.sampled_from(["", "hi", "<img src=x onerror=alert(1)>", "</noscript><script>x</script>",
                                 "<!--x-->", "-->"]))
    return "<%s%s>%s%s</%s>" % (tag, attr_s, text, children, tag)


from lxml.html import defs
URL_ATTRS = set(defs.link_attrs) | {"xlink:href", "formaction"}
JS_RE = re.compile(r"^\s*(javascript|vbscript|livescript|jscript|mocha):", re.I)


@given(html_docs())
@settings(max_examples=1000, suppress_health_check=list(HealthCheck))
def test_default_clean_removes_javascript(html):
    out = clean_html("<div>%s</div>" % html)
    doc = lxml.html.fromstring(out)
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        assert el.tag != "script", out
        for k, v in el.attrib.items():
            assert not k.lower().startswith("on"), out
            if k in URL_ATTRS:
                assert not JS_RE.match(re.sub(r"[\t\n\r]", "", v)), out

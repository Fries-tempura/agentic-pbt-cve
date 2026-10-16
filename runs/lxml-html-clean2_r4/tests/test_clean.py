import re
from hypothesis import given, settings, strategies as st
from lxml_html_clean import Cleaner, clean_html
from lxml.html import fromstring

HEX = set("0123456789abcdefABCDEF")

def css_unescape(s):
    """CSS Syntax Level 3 escape handling (§4.3.7)."""
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] != "\n":
            j = i + 1
            if s[j] in HEX:
                k = j
                while k < len(s) and k - j < 6 and s[k] in HEX:
                    k += 1
                cp = int(s[j:k], 16)
                out.append(chr(cp) if 0 < cp <= 0x10FFFF and not 0xD800 <= cp <= 0xDFFF else "�")
                if k < len(s) and s[k] in " \t\n":
                    k += 1
                i = k
            else:
                out.append(s[j]); i = j + 1
        else:
            out.append(c); i += 1
    return "".join(out)

def css_strip_comments(s):
    return re.sub(r"/\*.*?\*/", "", s, flags=re.S)

def encode_char(c):
    choices = [st.just(c), st.just("\\%x " % ord(c)), st.just("\\%06x" % ord(c))]
    if c not in HEX and c not in "\n":
        choices.append(st.just("\\" + c))
    return st.one_of(choices)

def obfuscated(word):
    return st.tuples(*[encode_char(c) for c in word]).map("".join)

dangerous_css = st.one_of(
    st.tuples(st.just("@"), obfuscated("import"), st.just(" url(http://evil.example/x.css);")).map("".join),
    st.tuples(st.just("a{width:"), obfuscated("expression"), st.just("(alert(1))}")).map("".join),
    st.tuples(st.just("a{background:url("), obfuscated("javascript"), st.just(":alert(1))}")).map("".join),
)

@settings(max_examples=500)
@given(dangerous_css)
def test_style_tag_has_no_dangerous_css(css):
    out = clean_html("<div><style>%s</style><p>x</p></div>" % css)
    doc = fromstring(out)
    for el in doc.iter("style"):
        text = css_unescape(css_strip_comments(el.text or "")).lower()
        text = re.sub(r"\s+", "", text)
        assert "@import" not in text, (css, out)
        assert "expression(" not in text, (css, out)
        assert "javascript:" not in text, (css, out)

@settings(max_examples=500)
@given(dangerous_css)
def test_inline_style_has_no_dangerous_css(css):
    c = Cleaner(safe_attrs=frozenset(["style"]) | Cleaner.safe_attrs)
    out = c.clean_html('<div><p style="%s">x</p></div>' % css.replace('"', "&quot;"))
    doc = fromstring(out)
    for el in doc.iter():
        text = css_unescape(css_strip_comments(el.get("style") or "")).lower()
        text = re.sub(r"\s+", "", text)
        assert "@import" not in text, (css, out)
        assert "expression(" not in text, (css, out)
        assert "javascript:" not in text, (css, out)

ws = st.sampled_from(["", " ", "\t", "\n", "%20", "%09", "&#9;", "&#10;"])
@settings(max_examples=500)
@given(st.lists(st.tuples(st.sampled_from(list("javascript")), ws), min_size=10, max_size=10),
       st.sampled_from(["a href", "img src", "iframe src", "form action", "area href"]))
def test_no_javascript_urls(parts, tagattr):
    scheme = "".join(c for c, _ in parts)
    if scheme.lower() != "javascript":
        return
    url = "".join(c + w for c, w in parts) + ":alert(1)"
    tag, attr = tagattr.split()
    out = clean_html('<div><%s %s="%s">x</%s></div>' % (tag, attr, url, tag))
    doc = fromstring(out)
    for el in doc.iter():
        for v in el.attrib.values():
            norm = re.sub(r"[\s\x00-\x20]", "", v).lower()
            assert not norm.startswith("javascript:"), (url, out)

@settings(max_examples=300)
@given(st.lists(st.sampled_from(list("<>/=\"' abcdefghijklmnoprstuvwxyz!-:") + ["script", "onerror", "onclick", "style", "img", "svg", "math", "noscript", "iframe", "javascript:"]), max_size=40).map("".join))
def test_no_scripts_or_handlers(html):
    try:
        out = clean_html("<div>" + html + "</div>")
    except Exception as e:
        if "Document is empty" in str(e):
            return
        raise
    doc = fromstring(out)
    for el in doc.iter():
        if isinstance(el.tag, str):
            assert el.tag != "script", out
            for a in el.attrib:
                assert not a.lower().startswith("on"), out

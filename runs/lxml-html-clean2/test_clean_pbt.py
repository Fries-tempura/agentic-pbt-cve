import warnings

from hypothesis import given, settings, strategies as st
from lxml_html_clean import Cleaner, clean_html

HEX = "0123456789abcdefABCDEF"


def css_escape_char(c, mode):
    """Valid CSS escapes of character c (CSS Syntax Level 3, 4.3.7)."""
    if mode == 0:
        return c
    if mode == 1:
        return "\\%x " % ord(c)
    if mode == 2:
        return "\\%06x" % ord(c)
    # literal escape: backslash + non-hex, non-newline char is that char
    if c in HEX:
        return "\\%x " % ord(c)
    return "\\" + c


@st.composite
def css_obfuscated(draw, word):
    modes = draw(st.lists(st.integers(0, 3), min_size=len(word), max_size=len(word)))
    return "".join(css_escape_char(c, m) for c, m in zip(word, modes))


forbidden = st.sampled_from(["expression", "import"])


@settings(max_examples=500)
@given(st.data())
def test_style_tag_escaped_import_or_expression_removed(data):
    word = data.draw(forbidden)
    obf = data.draw(css_obfuscated(word))
    if word == "import":
        css = "@%s url(http://evil.example/x.css);" % obf
    else:
        css = "a { width: %s(alert(1)); }" % obf
    html = "<div><style>%s</style><p>x</p></div>" % css
    out = clean_html(html)
    # decode the output the way a browser's CSS tokenizer would
    cleaner = Cleaner()
    style_text = out.split("<style>")[1].split("</style>")[0] if "<style>" in out else ""
    decoded = cleaner._decode_css_unicode_escapes(style_text)
    import re
    decoded = re.sub(r"\\([^0-9a-fA-F\n])", r"\1", decoded).lower()
    assert "@import" not in decoded and "expression(" not in decoded, (html, out)


@settings(max_examples=500)
@given(st.data())
def test_inline_style_escaped_expression_removed(data):
    obf = data.draw(css_obfuscated("expression"))
    html = '<p style="width: %s(alert(1))">x</p>' % obf
    out = clean_html(html)
    import re
    from lxml.html import fromstring
    style = fromstring(out).get("style") or ""
    decoded = Cleaner()._decode_css_unicode_escapes(style)
    decoded = re.sub(r"\\([^0-9a-fA-F\n])", r"\1", decoded).lower()
    assert "expression(" not in decoded.replace(" ", ""), (html, out)


hosts = st.sampled_from(["good.com", "evil.com"])
seps = st.sampled_from(["", "\\", "@", "\\@", "/", "%40", "\t", ":80", "#", "?"])


@settings(max_examples=1000)
@given(st.sampled_from(["http", "https", "HTTP"]), hosts, seps, hosts, st.text(alphabet="/\\@:.", max_size=3))
def test_host_whitelist_only_allows_whitelisted_host(scheme, h1, sep, h2, extra):
    url = f"{scheme}://{h1}{sep}{h2}{extra}"
    c = Cleaner(host_whitelist=["good.com"])
    from lxml.html import fromstring
    el = fromstring('<iframe src="x"></iframe>')
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        allowed = c.allow_embedded_url(el, url)
    if allowed:
        from urllib.parse import urlsplit
        # browser (WHATWG) treats backslash like slash for special schemes
        normalized = url.replace("\\", "/")
        host = urlsplit(normalized).hostname
        assert host == "good.com", (url, host)


tag = st.sampled_from(["p", "div", "a", "style", "script", "noscript", "math", "svg",
                       "textarea", "title", "b", "iframe", "object", "form", "img"])
attr = st.sampled_from(['', ' href="javascript:alert(1)"', ' onclick="x()"', ' style="color:red"',
                        ' src="http://a/b"', ' title="</style><img src=x onerror=a()>"'])
text = st.sampled_from(["x", "<", ">", "&lt;", "/* <img> */", "</p>", "<!-- c -->", "&amp;"])


@st.composite
def html_frag(draw, depth=0):
    parts = []
    for _ in range(draw(st.integers(1, 3))):
        if depth < 3 and draw(st.booleans()):
            t = draw(tag)
            parts.append(f"<{t}{draw(attr)}>{draw(html_frag(depth + 1))}</{t}>")
        else:
            parts.append(draw(text))
    return "".join(parts)


@settings(max_examples=1000)
@given(html_frag())
def test_clean_html_idempotent(h):
    html = "<div>" + h + "</div>"
    once = clean_html(html)
    twice = clean_html(once)
    assert once == twice, (html, once, twice)

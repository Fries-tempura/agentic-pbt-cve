import re
from hypothesis import given, settings, strategies as st
from lxml_html_clean import Cleaner, clean_html

HEX = "0123456789abcdefABCDEF"

def css_unescape(s):
    """Reference CSS escape decoding per CSS Syntax Level 3, sec 4.3.7."""
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i+1] != "\n":
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

@st.composite
def obfuscated(draw, word):
    parts = []
    for ch in word:
        mode = draw(st.sampled_from(["plain", "hex", "literal"]))
        if mode == "hex" and ch not in "(:@":
            parts.append("\\%x%s" % (ord(ch), draw(st.sampled_from(["", " "]))))
        elif mode == "literal" and ch.isalpha() and ch.lower() not in "abcdef":
            parts.append("\\" + ch)
        else:
            parts.append(ch)
    return "".join(parts)

dangerous = st.sampled_from(["javascript:", "expression(", "@import"])

def is_dangerous(css):
    d = re.sub(r"/\*.*?\*/", "", css_unescape(css), flags=re.S)
    d = re.sub(r"\s+", "", d).lower()
    return "javascript:" in d or "expression(" in d or "@import" in d

@settings(max_examples=500)
@given(dangerous.flatmap(obfuscated))
def test_style_tag_has_no_dangerous_css(payload):
    html = "<div><style>a { background: url(%s) }</style></div>" % payload
    out = clean_html(html)
    m = re.search(r"<style>(.*?)</style>", out, re.S)
    assert m is None or not is_dangerous(m.group(1)), (payload, out)

@settings(max_examples=500)
@given(dangerous.flatmap(obfuscated))
def test_inline_style_has_no_dangerous_css(payload):
    from lxml.html import fromstring
    out = Cleaner(safe_attrs_only=False).clean_html('<div style="x: %s">t</div>' % payload)
    style = fromstring(out).get("style")
    assert style is None or not is_dangerous(style), (payload, out)

@settings(max_examples=300)
@given(st.text(alphabet="<>/=\"' abcdefhijlmnoprstvx:&#;()", max_size=60))
def test_idempotent(s):
    once = clean_html("<div>" + s + "</div>")
    assert clean_html(once) == once

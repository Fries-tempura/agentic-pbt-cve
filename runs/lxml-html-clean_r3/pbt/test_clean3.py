import re
from test_clean2 import *
from test_clean2 import docs, safe_clean
from hypothesis import assume
import lxml.html

CTRL = re.compile(r'&#x?0*(?:[0-8]|1[0-9a-f]?|2[0-9]|3[01]|x[0-1][0-9a-f]);|[\x00-\x1f]', re.I)

css_piece = st.sampled_from(["expression(alert(1))", "e/**/xpression(1)", "url(javascript:alert(1))",
    "url('java\\script:x')", "@import 'evil.css';", "@im\\port 'x';", "/* <img src=x onerror=1> */",
    "/* </style><img src=x onerror=1> */", "color: red;", "</noscript>", "<", "/*", "*/", "\\", " ",
    "behavior:url(x.htc)", "background:url(data:image/svg+xml;base64,AAA)", "x:url(data:image/png;base64,AA)",
    "javascript:", "&lt;img&gt;", "<!--", "-->", "\n", "e\nxpression(1)", "</style", "</STYLE ", "<svg/onload=1>"])
css = st.lists(css_piece, max_size=8).map("".join)

@st.composite
def styledoc(draw):
    wrapper = draw(st.sampled_from(["{}", "<div>{}</div>", "<svg>{}</svg>", "<math>{}</math>", "<noscript>{}</noscript>", "<template>{}</template>"]))
    c = draw(css)
    inner = draw(st.sampled_from([f"<style>{c}</style>", f"<p style=\"{c.replace(chr(34), '')}\">x</p>"]))
    return wrapper.format(inner) + draw(st.sampled_from(["", "<p>x</p>"]))

def is_sneaky(s):
    s2 = re.sub(r'/\*.*?\*/', '', s, flags=re.S).replace('\\', '')
    s2 = re.sub(r'\s+', '', s2).lower()
    return ('expression(' in s2 or '@import' in s2 or 'javascript:' in s2 or
            re.search(r'</?[a-z]', s.lower()) is not None or re.search(r'\son[a-z]+\s*=', s.lower()) is not None)

@settings(max_examples=3000, suppress_health_check=list(HealthCheck), deadline=None)
@given(styledoc())
def test_style_sanitized(h):
    out = safe_clean(h)
    if out is None:
        return
    doc = lxml.html.fromstring(out)
    for el in doc.iter('style'):
        assert not is_sneaky(el.text or ''), (h, out)
    for el in doc.xpath('//*[@style]'):
        assert not is_sneaky(el.get('style')), (h, out)

@settings(max_examples=3000, suppress_health_check=list(HealthCheck), deadline=None)
@given(docs | styledoc())
def test_idempotent_noctrl(h):
    assume(not CTRL.search(h))
    out = safe_clean(h)
    if out is None or not out.strip():
        return
    out2 = safe_clean(out)
    assert out2 == out, (h, out, out2)

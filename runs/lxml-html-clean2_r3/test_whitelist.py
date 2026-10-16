import re, warnings
from hypothesis import given, settings, strategies as st, HealthCheck
from lxml_html_clean import Cleaner
from lxml_html_clean.clean import fromstring

def browser_host(url):
    # simplified WHATWG URL parsing for special schemes http/https
    url = url.strip("".join(map(chr, range(0x21))))
    url = re.sub(r"[\t\n\r]", "", url)
    m = re.match(r"(?i)(https?):", url)
    if not m:
        return None
    rest = url[m.end():]
    rest = rest.lstrip("/\\")
    auth = re.split(r"[/\\?#]", rest, 1)[0]
    host = auth.rsplit("@", 1)[-1]
    host = re.sub(r":\d*$", "", host)
    return host.lower()

pieces = st.sampled_from(["https:", "http:", "HTTPS:", "//", "/", "\\", "@", ":", "#", "?",
                          "good.com", "evil.com", "\t", "\n", " ", "%40", ":80", "user", ".", "[", "]"])
url = st.lists(pieces, min_size=1, max_size=10).map("".join)

c = Cleaner(host_whitelist={"good.com"})

@settings(max_examples=5000, suppress_health_check=list(HealthCheck), deadline=None)
@given(url)
def test_whitelist_host(u):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        el = fromstring('<iframe src="x"></iframe>')
        el.set("src", u)
        try:
            allowed = c.allow_embedded_url(el, u)
        except ValueError:
            return
    if allowed:
        assert browser_host(u) == "good.com", (u, browser_host(u))

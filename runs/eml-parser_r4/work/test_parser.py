import time
from hypothesis import given, settings, strategies as st, HealthCheck
import eml_parser.parser as P

URL = st.builds(lambda h, t, p: f"https://{h}.{t}/{p}",
                st.from_regex(r"[a-z]{3,10}", fullmatch=True),
                st.sampled_from(["com", "org", "net", "lu"]),
                st.from_regex(r"[a-z0-9]{0,20}", fullmatch=True))

@settings(max_examples=500, suppress_health_check=list(HealthCheck))
@given(st.integers(0, 2000), URL, st.sampled_from([" ", "\n", "x", "a b "]))
def test_sliding_window_does_not_lose_urls(pad_len, url, fill):
    body = (fill * pad_len)[:pad_len] + " " + url + " " + "y " * 300
    ep = P.EmlParser()
    found = set()
    for s in ep.string_sliding_window_loop(body):
        found.update(ep.get_uri_ondata(s))
    assert url in found, (pad_len, url)

@settings(max_examples=300, suppress_health_check=list(HealthCheck))
@given(st.text(max_size=3000))
def test_sliding_window_covers_body(body):
    slices = list(P.EmlParser.string_sliding_window_loop(body))
    joined = "".join(slices)
    # every char of the body must be in some slice: check by length lower bound
    assert len(joined) >= len(body)

@settings(max_examples=500, suppress_health_check=list(HealthCheck))
@given(st.binary(max_size=2000))
def test_decode_bytes_no_crash(b):
    P.EmlParser().decode_email_bytes(b)

hdr = st.sampled_from(["From", "To", "Cc", "Subject", "Date", "Received", "Message-ID", "Content-Type", "Content-Disposition", "Content-Transfer-Encoding", "X-Foo"])
val = st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\r\n"), max_size=80)

@settings(max_examples=1000, suppress_health_check=list(HealthCheck))
@given(st.lists(st.tuples(hdr, val), max_size=8), st.text(max_size=500))
def test_decode_structured_no_crash(headers, body):
    raw = "".join(f"{k}: {v}\n" for k, v in headers) + "\n" + body
    P.EmlParser(include_raw_body=True).decode_email_bytes(raw.encode("utf-8", "surrogatepass"))

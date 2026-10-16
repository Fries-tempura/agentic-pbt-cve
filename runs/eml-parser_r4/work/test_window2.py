import time
from hypothesis import given, settings, strategies as st, HealthCheck
import eml_parser.parser as P

URL = st.builds(lambda h, p: f"http://{h}.com/{p}",
                st.from_regex(r"[a-z]{3,8}", fullmatch=True),
                st.from_regex(r"[a-z0-9]{0,15}", fullmatch=True))
sep = st.sampled_from([" ", "\n", "\t", " > ", "  ", "\r\n"])

@settings(max_examples=500, suppress_health_check=list(HealthCheck), deadline=None)
@given(st.lists(st.tuples(st.text(alphabet="ab \n", max_size=60), sep, URL, sep), min_size=1, max_size=60))
def test_all_urls_found(parts):
    body = "".join(f + s1 + u + s2 for f, s1, u, s2 in parts)
    ep = P.EmlParser()
    found = set()
    n = 0
    for s in ep.string_sliding_window_loop(body):
        n += len(s)
        found.update(ep.get_uri_ondata(s))
    expected = {u for _, _, u, _ in parts}
    assert expected <= found, (expected - found)
    assert n <= 3 * len(body) + 1000

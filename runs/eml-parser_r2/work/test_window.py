import re
from hypothesis import given, settings, strategies as st, HealthCheck
from eml_parser.parser import EmlParser

word = st.from_regex(r"[a-z]{1,10}", fullmatch=True)
url = st.from_regex(r"https?://[a-z]{1,10}\.(com|org)/[a-z]{0,10}", fullmatch=True)
token = st.one_of(word, word, word, url)
sep = st.sampled_from([" ", "\n", " ", "  "])
bodies = st.lists(st.tuples(token, sep), min_size=1, max_size=400).map(lambda l: "".join(a + b for a, b in l))

@settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(bodies)
def test_urls_not_cut(body):
    slices = list(EmlParser.string_sliding_window_loop(body))
    for m in re.finditer(r"https?://[a-z.]+/[a-z]*", body):
        assert any(m.group(0) in s for s in slices), (m.group(0), [s[-30:] for s in slices])

@settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(bodies)
def test_words_not_lost(body):
    slices = list(EmlParser.string_sliding_window_loop(body))
    joined = "\x00".join(slices)
    for m in re.finditer(r"\S+", body):
        assert m.group(0)[:1] in joined
    # every char of body is in some slice: total covered length >= len(body)
    assert sum(map(len, slices)) >= len(body)

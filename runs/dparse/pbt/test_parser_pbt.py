import time
from hypothesis import given, settings, strategies as st, HealthCheck
from dparse.parser import Parser
from dparse import parse, filetypes

label = st.from_regex(r"\A[a-z0-9]([a-z0-9-]{0,10}[a-z0-9])?\Z")
tld = st.from_regex(r"\A[a-z]{2,6}\Z")
path = st.from_regex(r"\A(/[a-z0-9_.-]{1,8}){0,3}\Z")
opt = st.sampled_from(["-i ", "--index-url ", "--extra-index-url ", "--index-url=", "-i="])


@given(opt, st.sampled_from(["http", "https"]), st.lists(label, min_size=1, max_size=3), tld, path)
def test_index_server_roundtrip(o, scheme, labels, t, p):
    url = f"{scheme}://{'.'.join(labels)}.{t}{p}"
    res = Parser.parse_index_server(o + url)
    assert res == (url if url.endswith("/") else url + "/")


@given(st.sampled_from(["10.0.0.5", "192.168.1.10", "127.0.0.1", "172.16.0.3"]),
       st.sampled_from(["", ":8080"]))
def test_index_server_private_ip(ip, port):
    url = f"http://{ip}{port}/simple/"
    assert Parser.parse_index_server("-i " + url) == url


@settings(max_examples=30, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.integers(min_value=18, max_value=26), st.sampled_from(["a", "a-", "1"]),
       st.sampled_from(["!", "_", " ", "-"]))
def test_index_server_linear_time(n, unit, tail):
    line = "-i https://" + unit * n + tail
    t0 = time.perf_counter()
    Parser.parse_index_server(line)
    assert time.perf_counter() - t0 < 1.0, (n, unit, tail)


@settings(max_examples=50, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.sampled_from(["https://", "http://", "ftp://", "a", "a-", "a."]),
       st.integers(min_value=1, max_value=600))
def test_requirements_parse_scales_linearly(unit, n):
    content = "--index-url " + unit * n + "\ndjango\n"
    t0 = time.perf_counter()
    parse(content, file_type=filetypes.requirements_txt)
    assert time.perf_counter() - t0 < 0.5, (unit, n, len(content))


@settings(deadline=None)
@given(st.text(max_size=200))
def test_requirements_parse_no_crash(content):
    parse(content, file_type=filetypes.requirements_txt)

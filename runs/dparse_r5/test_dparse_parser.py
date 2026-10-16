import time
from hypothesis import given, settings, strategies as st, HealthCheck
from dparse import parse, filetypes
from dparse.parser import Parser

host_label = st.from_regex(r"[a-z0-9]{1,10}", fullmatch=True)
urls = st.builds(lambda scheme, labels, tld, path: f"{scheme}://{'.'.join(labels)}.{tld}{path}",
                 st.sampled_from(["http", "https"]), st.lists(host_label, min_size=1, max_size=3),
                 st.from_regex(r"[a-z]{2,5}", fullmatch=True),
                 st.sampled_from(["", "/", "/simple", "/simple/", "/a/b"]))

@given(st.sampled_from(["-i ", "--index-url ", "--index-url=", "--extra-index-url "]), urls)
def test_index_server_roundtrip(prefix, url):
    res = Parser.parse_index_server(prefix + url)
    assert res == (url if url.endswith("/") else url + "/")

# index server line in requirements file is attached to following deps
@given(urls, st.from_regex(r"[a-z][a-z0-9]{0,8}", fullmatch=True))
def test_requirements_index_server_attached(url, name):
    content = f"-i {url}\n{name}==1.0\n"
    df = parse(content, file_type=filetypes.requirements_txt)
    assert len(df.dependencies) == 1
    assert df.dependencies[0].index_server == (url if url.endswith("/") else url + "/")

# parsing must terminate quickly on arbitrary lines (no catastrophic backtracking)
@settings(max_examples=200, suppress_health_check=list(HealthCheck), deadline=None)
@given(st.sampled_from(["-i ", "--index-url "]),
       st.sampled_from(["http://", "https://", "ftp://"]),
       st.text(alphabet="a1-.", min_size=0, max_size=40))
def test_index_server_fast(prefix, scheme, body):
    t = time.time()
    Parser.parse_index_server(prefix + scheme + body)
    assert time.time() - t < 1.0, (prefix + scheme + body)

@given(st.from_regex(r"[a-z][a-z0-9]{0,8}", fullmatch=True),
       st.lists(st.from_regex(r"[a-f0-9]{8,64}", fullmatch=True), min_size=1, max_size=3))
def test_hashes_extracted(name, hs):
    line = f"{name}==1.0 " + " ".join(f"--hash=sha256:{h}" for h in hs)
    df = parse(line, file_type=filetypes.requirements_txt)
    assert len(df.dependencies) == 1
    assert df.dependencies[0].hashes == [f"--hash=sha256:{h}" for h in hs]

@settings(max_examples=500)
@given(st.text())
def test_requirements_no_crash(text):
    parse(text, file_type=filetypes.requirements_txt)


# A single index-url line of a few KB must be parsed in bounded time.
@settings(max_examples=100, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.builds(lambda a, b: a + b, st.sampled_from(["http://", "https://", "ftp://"]),
                 st.text(alphabet="a:@.-1/", max_size=4)), st.integers(100, 800))
def test_index_server_line_bounded_time(unit, reps):
    line = "--index-url " + unit * reps
    t = time.time()
    parse(line + "\nrequests==2.0\n", file_type=filetypes.requirements_txt)
    assert time.time() - t < 2.0, (unit, reps, len(line))

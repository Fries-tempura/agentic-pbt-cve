import time
from hypothesis import given, settings, strategies as st, HealthCheck
from dparse import parse, filetypes
from dparse.parser import Parser

name = st.from_regex(r"[a-zA-Z][a-zA-Z0-9]{0,10}", fullmatch=True)
version = st.from_regex(r"[0-9]{1,3}(\.[0-9]{1,3}){0,2}", fullmatch=True)
host_label = st.from_regex(r"[a-z0-9]{1,8}", fullmatch=True)

@given(st.lists(st.tuples(name, version), min_size=1, max_size=10, unique_by=lambda t: t[0].lower()))
def test_requirements_roundtrip(pkgs):
    content = "\n".join(f"{n}=={v}" for n, v in pkgs)
    df = parse(content, file_type=filetypes.requirements_txt)
    assert [d.name for d in df.dependencies] == [n for n, _ in pkgs]
    assert [str(d.specs) for d in df.dependencies] == [f"=={v}" for _, v in pkgs]

@given(st.lists(host_label, min_size=1, max_size=4), st.from_regex(r"[a-z]{2,6}", fullmatch=True), name, version)
def test_index_server(labels, tld, n, v):
    url = "https://" + ".".join(labels) + "." + tld + "/simple"
    content = f"-i {url}\n{n}=={v}"
    df = parse(content, file_type=filetypes.requirements_txt)
    assert df.dependencies[0].index_server == url + "/"

# single entry point: parsing a requirements line with an index-url must not hang
@settings(max_examples=200, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.text(alphabet="abc0-.", min_size=0, max_size=40))
def test_index_url_line_is_fast(tail):
    line = "--index-url https://" + tail
    t = time.perf_counter()
    Parser.parse_index_server(line)
    assert time.perf_counter() - t < 1.0, len(tail)

# Parsing a requirements file of a few KB should finish quickly (linear-ish), whatever its content.
@settings(max_examples=50, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.lists(st.sampled_from(["https://", "http://", ":", "@", "a", ".", "/"]), min_size=1, max_size=20),
       st.integers(min_value=1, max_value=600))
def test_parse_requirements_index_line_not_quadratic(chunks, reps):
    content = "--index-url " + "".join(chunks) * reps + "\nrequests==2.0\n"
    t = time.perf_counter()
    parse(content, file_type=filetypes.requirements_txt)
    assert time.perf_counter() - t < 2.0, (len(content))

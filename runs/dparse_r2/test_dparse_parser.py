import time
from hypothesis import given, settings, strategies as st, HealthCheck
from dparse import parse, filetypes
from dparse.parser import Parser

host = st.from_regex(r"[a-z][a-z0-9]{0,10}(\.[a-z][a-z0-9]{0,10}){0,3}\.[a-z]{2,6}", fullmatch=True)
path = st.from_regex(r"(/[a-zA-Z0-9_\-]{0,10}){0,4}", fullmatch=True)

@given(host, path, st.sampled_from(["-i ", "--index-url ", "--extra-index-url ", "--index-url="]))
def test_index_server_roundtrip(h, p, flag):
    url = "https://" + h + p
    res = Parser.parse_index_server(flag + url)
    assert res == (url if url.endswith("/") else url + "/")

@settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.text(alphabet="ab.-:/@1 \t", min_size=0, max_size=60))
def test_index_server_fast(s):
    line = "-i https://" + s * 4
    t = time.perf_counter()
    Parser.parse_index_server(line)
    assert time.perf_counter() - t < 1.0, repr(line)

name = st.from_regex(r"[A-Za-z][A-Za-z0-9_\-]{0,10}[A-Za-z0-9]", fullmatch=True)
ver = st.from_regex(r"[0-9]{1,3}(\.[0-9]{1,3}){0,2}", fullmatch=True)

@given(st.lists(st.tuples(name, st.sampled_from(["==", ">=", "<=", "!="]), ver), min_size=1, max_size=5, unique_by=lambda t: t[0].lower()))
def test_requirements_names(reqs):
    content = "\n".join(n + op + v for n, op, v in reqs)
    df = parse(content, file_type=filetypes.requirements_txt)
    assert [d.name for d in df.dependencies] == [n for n, _, _ in reqs]
    assert [str(d.specs) for d in df.dependencies] == [op + v for _, op, v in reqs]

@settings(max_examples=500)
@given(st.text())
def test_requirements_no_crash(s):
    parse(s, file_type=filetypes.requirements_txt)

@settings(max_examples=300)
@given(st.text())
def test_pipfile_no_crash(s):
    parse(s, file_type=filetypes.pipfile)

import time
from hypothesis import given, settings, strategies as st, HealthCheck
from dparse import parse, filetypes
from dparse.parser import Parser

name = st.from_regex(r"\A[a-z][a-z0-9]{0,10}\Z")
version = st.from_regex(r"\A[0-9]{1,3}(\.[0-9]{1,3}){0,2}\Z")
label = st.from_regex(r"\A[a-z0-9]{1,10}\Z")
host = st.builds(lambda parts, tld: ".".join(parts + [tld]),
                 st.lists(label, min_size=1, max_size=4), st.from_regex(r"\A[a-z]{2,6}\Z"))


@given(st.lists(st.tuples(name, version), min_size=1, max_size=10, unique_by=lambda t: t[0]))
def test_pinned_requirements_roundtrip(reqs):
    content = "\n".join(f"{n}=={v}" for n, v in reqs)
    df = parse(content, file_type=filetypes.requirements_txt)
    got = [(d.name, str(d.specs)) for d in df.dependencies]
    assert got == [(n, f"=={v}") for n, v in reqs]


@given(name, version, st.lists(st.from_regex(r"\A[0-9a-f]{8,64}\Z"), min_size=1, max_size=3))
def test_hashes_extracted(n, v, hs):
    line = f"{n}=={v} " + " ".join(f"--hash=sha256:{h}" for h in hs)
    df = parse(line, file_type=filetypes.requirements_txt)
    assert len(df.dependencies) == 1
    d = df.dependencies[0]
    assert d.name == n and str(d.specs) == f"=={v}"
    assert d.hashes == [f"--hash=sha256:{h}" for h in hs]


@given(st.sampled_from(["-i ", "--index-url ", "--extra-index-url "]),
       st.sampled_from(["http", "https"]), host,
       st.from_regex(r"\A(/[a-z0-9]{1,8}){0,3}\Z"), name, version)
def test_index_server(opt, scheme, h, path, n, v):
    url = f"{scheme}://{h}{path}"
    content = f"{opt}{url}\n{n}=={v}"
    df = parse(content, file_type=filetypes.requirements_txt)
    assert len(df.dependencies) == 1
    exp = url if url.endswith("/") else url + "/"
    assert df.dependencies[0].index_server == exp


@settings(deadline=None, suppress_health_check=list(HealthCheck))
@given(st.text(alphabet="ab1.-:/@ ", min_size=0, max_size=60))
def test_parse_index_server_fast(tail):
    line = "-i https://" + tail * 1
    t = time.perf_counter()
    Parser.parse_index_server(line)
    assert time.perf_counter() - t < 0.5


@given(st.lists(label, min_size=1, max_size=3), st.from_regex(r"\A[a-z0-9_\-]{1,10}\.txt\Z"))
def test_resolve_file(dirs, fname):
    path = "/".join(dirs) + "/requirements.txt"
    df = parse(f"-r {fname}", file_type=filetypes.requirements_txt, path=path)
    assert df.resolved_files == ["/".join(dirs) + "/" + fname]


@settings(max_examples=500)
@given(st.text())
def test_requirements_no_crash(content):
    parse(content, file_type=filetypes.requirements_txt)


@settings(deadline=None, max_examples=50, suppress_health_check=list(HealthCheck))
@given(st.text(alphabet="a1-.", min_size=1, max_size=4), st.integers(10, 40),
       st.sampled_from(["", "!", " ", ".", "-"]))
def test_parse_index_server_linear_time(chunk, reps, end):
    line = "-i https://" + chunk * reps + end
    t = time.perf_counter()
    Parser.parse_index_server(line)
    assert time.perf_counter() - t < 1.0, (line, time.perf_counter() - t)

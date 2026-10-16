import http, logging
from urllib.parse import quote, unquote
from hypothesis import given, settings, strategies as st
from uvicorn.logging import AccessFormatter, ColourizedFormatter
from uvicorn.protocols.utils import get_path_with_query_string

ACCESS_FMT = '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_codes)s'

def make_record(scope, status):
    rec = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1,
        '%s - "%s %s HTTP/%s" %d', ("", scope["method"], "", "1.1", status), None)
    rec.status_code = status
    rec.scope = scope
    return rec

# raw request-target bytes as h11 would accept them (visible ASCII), then decoded as h11_impl does
raw_target = st.text(alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7e, blacklist_characters="?#"), min_size=0).map(lambda s: "/" + s)
query = st.text(alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7e, blacklist_characters="#"))

def scope_from(raw_path, qs, client):
    return {"type": "http", "method": "GET", "http_version": "1.1",
            "path": unquote(raw_path), "root_path": "",
            "query_string": qs.encode("ascii"), "client": client}

client = st.one_of(st.none(), st.tuples(st.sampled_from(["127.0.0.1", "::1", "10.0.0.2"]), st.integers(0, 65535)))
status = st.integers(100, 599)

@settings(max_examples=1000)
@given(raw_target, query, client, status)
def test_access_log_is_single_line(raw_path, qs, cl, code):
    """One access log record must render as exactly one log line."""
    f = AccessFormatter(fmt='%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False)
    out = f.format(make_record(scope_from(raw_path, qs, cl), code))
    assert "\n" not in out and "\r" not in out, repr(out)

@settings(max_examples=1000)
@given(st.text(), query, client, status)
def test_full_path_matches_protocol_helper(path, qs, cl, code):
    scope = scope_from("/", qs, cl); scope["path"] = "/" + path
    f = AccessFormatter(use_colors=False)
    assert f.get_full_path(scope) == get_path_with_query_string(scope)

@given(client)
def test_client_addr(cl):
    scope = {"client": cl}
    exp = "" if not cl else f"{cl[0]}:{cl[1]}"
    assert AccessFormatter(use_colors=False).get_client_addr(scope) == exp

@given(status)
def test_status_code_plain(code):
    rec = make_record(scope_from("/", "", None), code)
    out = AccessFormatter(use_colors=False).get_status_code(rec)
    assert out.startswith(str(code))
    try:
        assert out == f"{code} {http.HTTPStatus(code).phrase}"
    except ValueError:
        pass

@given(st.sampled_from([5, 10, 20, 30, 40, 50]))
def test_levelprefix_alignment(level):
    if level == 5: logging.addLevelName(5, "TRACE")
    f = ColourizedFormatter(fmt="%(levelprefix)s|%(message)s", use_colors=False)
    rec = logging.LogRecord("x", level, __file__, 1, "hi", (), None)
    out = f.format(rec)
    assert out.index("|") == 9, repr(out)

pct = st.integers(0, 255).map(lambda b: "%%%02X" % b)
plain = st.characters(min_codepoint=0x21, max_codepoint=0x7e, blacklist_characters="?#%")
raw_target2 = st.lists(st.one_of(plain, pct)).map(lambda xs: "/" + "".join(xs))

@settings(max_examples=1000)
@given(raw_target2, query, client, status)
def test_access_log_is_single_line_pct(raw_path, qs, cl, code):
    f = AccessFormatter(fmt='%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False)
    out = f.format(make_record(scope_from(raw_path, qs, cl), code))
    assert "\n" not in out and "\r" not in out, repr(out)

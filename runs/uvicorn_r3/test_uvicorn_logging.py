import logging
from urllib.parse import quote, unquote

from hypothesis import given, settings, strategies as st

from uvicorn.logging import AccessFormatter

FMT = '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'

# raw request targets as a client may send them (percent-encoded ASCII),
# decoded exactly like uvicorn/protocols/http/h11_impl.py does
raw_targets = st.text().map(lambda s: "/" + quote(s, safe="/"))


def make_record(scope, status_code=200):
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1,
        '%s - "%s %s HTTP/%s" %d', (), None,
    )
    record.scope = scope
    record.status_code = status_code
    return record


def scope_for(raw_target):
    return {
        "type": "http", "method": "GET", "http_version": "1.1",
        "root_path": "", "path": unquote(raw_target),
        "query_string": b"", "client": ("127.0.0.1", 12345),
    }


@given(raw_targets, st.integers(min_value=100, max_value=599))
@settings(max_examples=500)
def test_no_colors_means_no_escape_codes(raw_target, status):
    fmt = AccessFormatter(fmt=FMT, use_colors=False)
    out = fmt.format(make_record(scope_for(raw_target), status))
    assert "\x1b" not in out, repr(out)


@given(raw_targets)
@settings(max_examples=500)
def test_access_log_is_single_line(raw_target):
    fmt = AccessFormatter(fmt=FMT, use_colors=False)
    out = fmt.format(make_record(scope_for(raw_target)))
    assert "\n" not in out and "\r" not in out, repr(out)


@given(raw_targets, st.integers(min_value=100, max_value=599))
def test_colored_status_and_levelprefix(raw_target, status):
    fmt = AccessFormatter(fmt=FMT, use_colors=True)
    out = fmt.format(make_record(scope_for(raw_target), status))
    assert str(status) in out

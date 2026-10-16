import logging
from urllib.parse import unquote, quote

from hypothesis import given, settings, strategies as st

from uvicorn.config import LOGGING_CONFIG
from uvicorn.logging import AccessFormatter, DefaultFormatter

ACCESS_FMT = LOGGING_CONFIG["formatters"]["access"]["fmt"]

# Raw request-target paths as they appear on the wire: printable ASCII plus
# percent-encoded arbitrary bytes (what h11/httptools accept).
pct = st.integers(0, 255).map(lambda b: "%%%02X" % b)
safe_char = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~/!$&'()*+,;=:@"
)
raw_path = st.lists(st.one_of(safe_char, pct)).map(lambda xs: "/" + "".join(xs))


def make_record(raw, status=200, query=b""):
    # Mirrors h11_impl: "path": unquote(raw_path.decode("ascii"))
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": unquote(raw),
        "root_path": "",
        "query_string": query,
        "client": ("127.0.0.1", 12345),
    }
    return logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, "", (), None,
        # extra fields as passed by the protocol implementations
    ), scope, status


def fmt(raw, use_colors=False, status=200):
    rec, scope, status = make_record(raw, status)
    rec.__dict__.update({"scope": scope, "status_code": status})
    return AccessFormatter(fmt=ACCESS_FMT, use_colors=use_colors).format(rec)


@settings(max_examples=1000)
@given(raw_path, st.booleans())
def test_access_log_is_single_line(raw, use_colors):
    line = fmt(raw, use_colors)
    assert "\n" not in line and "\r" not in line, repr(line)


@settings(max_examples=1000)
@given(raw_path)
def test_access_log_has_no_terminal_escapes_when_uncoloured(raw):
    line = fmt(raw, use_colors=False)
    assert "\x1b" not in line, repr(line)


@given(st.integers(100, 599), st.booleans())
def test_status_code_in_output(status, use_colors):
    line = fmt("/", use_colors, status)
    assert str(status) in line


@given(st.sampled_from([5, 10, 20, 30, 40, 50]), st.text(), st.booleans())
def test_default_formatter_levelprefix(level, msg, use_colors):
    rec = logging.LogRecord("uvicorn.error", level, __file__, 1, msg, (), None)
    out = DefaultFormatter(fmt="%(levelprefix)s %(message)s", use_colors=use_colors).format(rec)
    assert out.endswith(" " + msg) or msg == "" 
    assert logging.getLevelName(level) in out if level != 5 else True

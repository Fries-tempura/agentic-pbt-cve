import logging
import string
from urllib.parse import quote, unquote

from hypothesis import given, settings, strategies as st

from uvicorn.config import LOGGING_CONFIG
from uvicorn.logging import AccessFormatter, DefaultFormatter

ACCESS_FMT = LOGGING_CONFIG["formatters"]["access"]["fmt"]
DEFAULT_FMT = LOGGING_CONFIG["formatters"]["default"]["fmt"]

# Raw request targets as an attacker could send them: printable ASCII,
# with arbitrary bytes percent-encoded (exactly what h11_impl unquotes).
raw_segment = st.text(alphabet=string.ascii_letters + string.digits + "-._~/", max_size=10)
any_char = st.characters(min_codepoint=0, max_codepoint=0x7F)


@st.composite
def raw_paths(draw):
    parts = draw(st.lists(st.one_of(raw_segment, any_char.map(lambda c: quote(c, safe=""))), max_size=6))
    return "/" + "".join(parts)


def make_record(scope, status=200):
    return logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1,
        '%s - "%s %s HTTP/%s" %d', ("x", "GET", "/", "1.1", status), None,
    ) if False else _rec(scope, status)


def _rec(scope, status):
    r = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, "msg", (), None)
    r.status_code = status
    r.scope = scope
    return r


def scope_for(raw_path, query=b""):
    return {
        "type": "http", "method": "GET", "http_version": "1.1",
        "path": unquote(raw_path),  # as in protocols/http/h11_impl.py
        "raw_path": raw_path.encode(), "query_string": query,
        "root_path": "", "client": ("127.0.0.1", 12345),
    }


@settings(max_examples=500)
@given(raw_paths())
def test_access_log_single_line(raw_path):
    fmt = AccessFormatter(fmt=ACCESS_FMT, use_colors=False)
    out = fmt.format(_rec(scope_for(raw_path), 200))
    assert "\n" not in out and "\r" not in out, repr(out)


@settings(max_examples=500)
@given(raw_paths())
def test_no_ansi_when_colors_disabled(raw_path):
    fmt = AccessFormatter(fmt=ACCESS_FMT, use_colors=False)
    out = fmt.format(_rec(scope_for(raw_path), 200))
    assert "\x1b" not in out, repr(out)


@given(st.sampled_from([5, 10, 20, 30, 40, 50]), st.text(), st.booleans())
def test_default_formatter_no_ansi_when_disabled(level, msg, colors):
    fmt = DefaultFormatter(fmt=DEFAULT_FMT, use_colors=colors)
    msg = msg.replace("\x1b", "")
    r = logging.LogRecord("uvicorn.error", level, __file__, 1, msg, (), None)
    r.color_message = msg
    out = fmt.format(r)
    if not colors:
        assert "\x1b" not in out
    assert out.endswith(" " + msg) or out.endswith(msg)
    assert r.__dict__.get("levelprefix") is None  # record not mutated

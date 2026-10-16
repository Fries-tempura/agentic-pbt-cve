import logging
import re
from urllib.parse import quote, unquote

from hypothesis import given, settings, strategies as st

from uvicorn.logging import AccessFormatter, ColourizedFormatter

ACCESS_FMT = '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
ANSI = re.compile(r"\x1b")


def make_record(scope, status_code=200):
    return logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1,
        '%s - "%s %s HTTP/%s" %d', (), None,
    ) if False else _rec(scope, status_code)


def _rec(scope, status_code):
    r = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, "msg", (), None)
    r.scope = scope
    r.status_code = status_code
    return r


# Raw request targets as they come off the wire: printable ASCII with
# percent-escapes. The protocol layer computes scope["path"] = unquote(raw).
raw_path = st.lists(
    st.one_of(
        st.sampled_from(list("abcxyz/-._~")),
        st.integers(0, 255).map(lambda b: "%%%02X" % b),
    ),
    min_size=0,
).map(lambda parts: "/" + "".join(parts))


@settings(max_examples=500)
@given(raw_path, st.sampled_from([200, 404, 500]))
def test_access_log_is_single_line_without_terminal_escapes(raw, status):
    scope = {
        "type": "http",
        "method": "GET",
        "path": unquote(raw),
        "root_path": "",
        "query_string": b"",
        "http_version": "1.1",
        "client": ("127.0.0.1", 12345),
    }
    fmt = AccessFormatter(fmt=ACCESS_FMT, use_colors=False)
    out = fmt.format(_rec(scope, status))
    assert "\n" not in out and "\r" not in out, repr(out)
    assert not ANSI.search(out), repr(out)


@given(st.sampled_from([5, 10, 20, 30, 40, 50]), st.text())
def test_no_colors_means_no_ansi(level, msg):
    if level == 5:
        logging.addLevelName(5, "TRACE")
    fmt = ColourizedFormatter(fmt="%(levelprefix)s %(message)s", use_colors=False)
    r = logging.LogRecord("x", level, __file__, 1, "%s", (msg.replace("\x1b", ""),), None)
    out = fmt.format(r)
    assert "\x1b" not in out
    name = logging.getLevelName(level)
    assert out.startswith(name + ":")

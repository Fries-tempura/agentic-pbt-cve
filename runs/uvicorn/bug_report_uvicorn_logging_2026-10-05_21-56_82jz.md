# Bug Report: uvicorn.logging AccessFormatter writes raw control characters from the request path into logs

**Target**: `uvicorn.logging.AccessFormatter`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`AccessFormatter` puts `scope["path"]` into the access log line as-is. That value has already been percent-decoded by the protocol layer (`unquote(...)` in `h11_impl.py` and `httptools_impl.py`). A remote client can therefore put a CR, LF or ESC byte in the URL as `%0D`, `%0A` or `%1B`. Those bytes reach the log unescaped, so the client can forge log lines or inject terminal escape sequences. This happens even with `use_colors=False`.

## Property-Based Test

```python
import logging, re
from urllib.parse import unquote
from hypothesis import given, settings, strategies as st
from uvicorn.logging import AccessFormatter

ACCESS_FMT = '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'

def _rec(scope, status_code):
    r = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, "msg", (), None)
    r.scope = scope
    r.status_code = status_code
    return r

raw_path = st.lists(
    st.one_of(
        st.sampled_from(list("abcxyz/-._~")),
        st.integers(0, 255).map(lambda b: "%%%02X" % b),
    ),
).map(lambda parts: "/" + "".join(parts))

@settings(max_examples=500)
@given(raw_path, st.sampled_from([200, 404, 500]))
def test_access_log_is_single_line_without_terminal_escapes(raw, status):
    scope = {"type": "http", "method": "GET", "path": unquote(raw), "root_path": "",
             "query_string": b"", "http_version": "1.1", "client": ("127.0.0.1", 12345)}
    out = AccessFormatter(fmt=ACCESS_FMT, use_colors=False).format(_rec(scope, status))
    assert "\n" not in out and "\r" not in out, repr(out)
    assert "\x1b" not in out, repr(out)
```

**Failing input**: `raw='/%1B'` (ESC in the log) and `raw='/%0D'` (CR in the log)

## Reproducing the Bug

```python
import logging
from urllib.parse import unquote
from uvicorn.logging import AccessFormatter

fmt = AccessFormatter(fmt='%(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False)
r = logging.LogRecord("uvicorn.access", logging.INFO, "", 1, "", (), None)
r.status_code = 200
r.scope = {
    "method": "GET",
    "path": unquote("/x%0D%0A127.0.0.1:1 - \"GET /admin HTTP/1.1\" 200 OK%1B[2J"),
    "query_string": b"",
    "http_version": "1.1",
    "client": ("10.0.0.5", 4242),
}
print(repr(fmt.format(r)))
```

Output:
```
'10.0.0.5:4242 - "GET /x\r\n127.0.0.1:1 - "GET /admin HTTP/1.1" 200 OK\x1b[2J HTTP/1.1" 200 OK'
```

## Why This Is A Bug

Access logs are supposed to hold one request per line, and with `use_colors=False` they should contain no ANSI codes. Any unauthenticated client can break both rules: it can forge log entries with CR/LF and clear or hijack an operator's terminal with ESC sequences. This is CVE-2020-7694 (log injection / terminal escape injection in uvicorn < 0.11.7). Other loggers avoid this by re-quoting the decoded path before writing it out.

## Fix

```diff
--- a/uvicorn/logging.py
+++ b/uvicorn/logging.py
@@
 import http
 import logging
 import sys
 from copy import copy
+from urllib.parse import quote
 
 import click
@@
     def get_path(self, scope):
-        return scope.get("root_path", "") + scope["path"]
+        return quote(scope.get("root_path", "") + scope["path"])
 
     def get_full_path(self, scope):
-        path = scope.get("root_path", "") + scope["path"]
+        path = quote(scope.get("root_path", "") + scope["path"])
         query_string = scope.get("query_string", b"").decode("ascii")
         if query_string:
             return path + "?" + query_string
         return path
```

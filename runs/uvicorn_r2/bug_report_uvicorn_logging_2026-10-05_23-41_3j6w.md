# Bug Report: uvicorn.logging AccessFormatter allows log injection via percent-decoded request path

**Target**: `uvicorn.logging.AccessFormatter`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`AccessFormatter` puts `scope["path"]` into the access log line without escaping it. The HTTP protocols fill that field with the *percent-decoded* request target (`unquote(raw_path)` in `protocols/http/h11_impl.py:201` and `httptools_impl.py:215`). A client can send `%0D%0A` to inject fake access-log lines, or `%1B` to emit raw ANSI terminal escape sequences, even when `use_colors=False` (CVE-2020-7694).

## Property-Based Test

```python
@settings(max_examples=500)
@given(raw_paths())   # "/" + mix of safe chars and percent-encoded ASCII bytes
def test_access_log_single_line(raw_path):
    fmt = AccessFormatter(fmt=ACCESS_FMT, use_colors=False)
    out = fmt.format(_rec(scope_for(raw_path), 200))   # scope["path"] = unquote(raw_path), as in h11_impl
    assert "\n" not in out and "\r" not in out, repr(out)
```

**Failing input**: `raw_path='/%0A'` → `'INFO:     127.0.0.1:12345 - "GET /\n HTTP/1.1" 200 OK'`

## Reproducing the Bug

```python
import logging
from urllib.parse import unquote
from uvicorn.config import LOGGING_CONFIG
from uvicorn.logging import AccessFormatter

fmt = AccessFormatter(fmt=LOGGING_CONFIG["formatters"]["access"]["fmt"], use_colors=False)
raw_path = '/%0D%0AINFO:     10.0.0.1:1 - "GET /admin HTTP/1.1" 200 OK%1b[2J'
record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "", (), None)
record.status_code = 404
record.scope = {"method": "GET", "http_version": "1.1", "path": unquote(raw_path),
                "query_string": b"", "client": ("127.0.0.1", 12345)}
print(repr(fmt.format(record)))
# 'INFO:     127.0.0.1:12345 - "GET /\r\nINFO:     10.0.0.1:1 - "GET /admin HTTP/1.1" 200 OK\x1b[2J HTTP/1.1" 404 Not Found'
```

## Why This Is A Bug

Each access-log record is supposed to be one line that shows the request line (`"%(request_line)s"`). Because the path is decoded before it is logged, a remote client controls raw CR, LF and ESC bytes in the log. The client can forge log entries, which defeats auditing and log parsing. It can also send terminal escape sequences to whoever reads the log in a terminal. `use_colors=False` does not prevent this, even though it should keep escape codes out of the output. The decoded path is also not the request line the client actually sent, which was `/%0D%0A...`.

## Fix

Log the request target as it appeared on the wire, which is the percent-encoded form, rather than the decoded path:

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
```

Apply the same `quote(...)` to `get_path_with_query_string` in `uvicorn/protocols/utils.py`, which builds the plain log message.

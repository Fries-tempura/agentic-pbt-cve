# Bug Report: uvicorn.logging AccessFormatter allows log injection via percent-encoded request path

**Target**: `uvicorn.logging.AccessFormatter`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`AccessFormatter` puts `scope["path"]` into the access log line without escaping it. Both protocol implementations fill that field with the **percent-decoded** request target (`unquote(...)`). A client can therefore send `%0D%0A` or `%1B` and get raw CR/LF or ANSI escape sequences into the log. This lets them forge extra access-log lines or inject terminal control sequences (log injection, CWE-117).

## Property-Based Test

```python
import logging
from urllib.parse import unquote
from hypothesis import given, settings, strategies as st
from uvicorn.config import LOGGING_CONFIG
from uvicorn.logging import AccessFormatter

ACCESS_FMT = LOGGING_CONFIG["formatters"]["access"]["fmt"]
pct = st.integers(0, 255).map(lambda b: "%%%02X" % b)
safe_char = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~/!$&'()*+,;=:@"
)
raw_path = st.lists(st.one_of(safe_char, pct)).map(lambda xs: "/" + "".join(xs))

def fmt(raw, use_colors=False, status=200):
    scope = {"type": "http", "http_version": "1.1", "method": "GET",
             "path": unquote(raw), "root_path": "", "query_string": b"",
             "client": ("127.0.0.1", 12345)}
    rec = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, "", (), None)
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
    assert "\x1b" not in fmt(raw, use_colors=False)
```

**Failing input**: `raw='/%0A'` (newline), `raw='/%1B'` (ESC)

## Reproducing the Bug

```python
import logging
from urllib.parse import unquote
from uvicorn.config import LOGGING_CONFIG
from uvicorn.logging import AccessFormatter

raw_target = "/x%0D%0AINFO:     6.6.6.6:1 - \"GET /admin HTTP/1.1\" 200 OK%1B[2J"
scope = {"type": "http", "http_version": "1.1", "method": "GET",
         "path": unquote(raw_target), "root_path": "", "query_string": b"",
         "client": ("127.0.0.1", 12345)}
record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "", (), None)
record.__dict__.update(scope=scope, status_code=200)
print(repr(AccessFormatter(LOGGING_CONFIG["formatters"]["access"]["fmt"], use_colors=False).format(record)))
# 'INFO:     127.0.0.1:12345 - "GET /x\r\nINFO:     6.6.6.6:1 - "GET /admin HTTP/1.1" 200 OK\x1b[2J HTTP/1.1" 200 OK'
```

This is the scope shape that `h11_impl.py` (`"path": unquote(raw_path.decode("ascii"))`) and `httptools_impl.py` (`urllib.parse.unquote(path)`) produce for the request line `GET /x%0D%0AINFO:...%1B[2J HTTP/1.1`, which is a valid HTTP request target.

## Why This Is A Bug

The default access format, `%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s`, writes one record per line, and the quoted `request_line` field stands for the request target as it arrived. Because the path is decoded first, a remote unauthenticated client controls raw control characters in the log. They can forge whole access-log entries (here, a fake `200 OK` for `/admin` from `6.6.6.6`) and send terminal escape sequences to anyone who views the log. This is CVE-2020-7694. The `get_path_with_query_string` helper in `uvicorn/protocols/utils.py`, used for the plain log message, has the same flaw.

## Fix

Re-quote the path before logging it, so the log shows the percent-encoded form that went over the wire:

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
--- a/uvicorn/protocols/utils.py
+++ b/uvicorn/protocols/utils.py
@@
 def get_path_with_query_string(scope):
-    path_with_query_string = scope.get("root_path", "") + scope["path"]
+    path_with_query_string = urllib.parse.quote(
+        scope.get("root_path", "") + scope["path"]
+    )
```

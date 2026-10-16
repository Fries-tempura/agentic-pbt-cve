# Bug Report: uvicorn.logging AccessFormatter allows log injection via percent-decoded request path

**Target**: `uvicorn.logging.AccessFormatter`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`AccessFormatter` puts `scope["path"]` straight into the access log line. Uvicorn has already percent-decoded that value (`unquote(raw_path)` in `h11_impl.py` and `httptools_impl.py`). A remote client can therefore send `%0A`, `%0D` or `%1B` in the URL and get raw newlines and ANSI escape sequences written to the log. That lets them forge log entries and inject terminal control codes, even with `use_colors=False`.

## Property-Based Test

```python
import logging
from urllib.parse import quote, unquote
from hypothesis import given, settings, strategies as st
from uvicorn.logging import AccessFormatter

FMT = '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
raw_targets = st.text().map(lambda s: "/" + quote(s, safe="/"))

def make_record(scope, status_code=200):
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, "", (), None)
    record.scope = scope
    record.status_code = status_code
    return record

def scope_for(raw_target):
    return {"type": "http", "method": "GET", "http_version": "1.1", "root_path": "",
            "path": unquote(raw_target), "query_string": b"", "client": ("127.0.0.1", 12345)}

@given(raw_targets, st.integers(min_value=100, max_value=599))
@settings(max_examples=500)
def test_no_colors_means_no_escape_codes(raw_target, status):
    out = AccessFormatter(fmt=FMT, use_colors=False).format(make_record(scope_for(raw_target), status))
    assert "\x1b" not in out

@given(raw_targets)
@settings(max_examples=500)
def test_access_log_is_single_line(raw_target):
    out = AccessFormatter(fmt=FMT, use_colors=False).format(make_record(scope_for(raw_target)))
    assert "\n" not in out and "\r" not in out
```

**Failing input**: `raw_target='/%1B'` (escape codes) and `raw_target='/%0A'` (newline)

## Reproducing the Bug

```python
import logging
from urllib.parse import unquote
from uvicorn.logging import AccessFormatter

fmt = AccessFormatter(fmt='%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False)
target = "/x%20HTTP/1.1%22%20200%0AINFO:%20%20%20%20%201.2.3.4:1%20-%20%22GET%20/admin"
r = logging.LogRecord("uvicorn.access", logging.INFO, "", 1, "", (), None)
r.scope = {"method": "GET", "http_version": "1.1", "root_path": "", "path": unquote(target),
           "query_string": b"", "client": ("127.0.0.1", 5000)}
r.status_code = 200
print(fmt.format(r))
```

Output (one request produces two forged log lines):
```
INFO:     127.0.0.1:5000 - "GET /x HTTP/1.1" 200
INFO:     1.2.3.4:1 - "GET /admin HTTP/1.1" 200 OK
```

If you use `/%1B[31mRED` as the target instead, a raw `\x1b[31m` ends up in the log even though `use_colors=False`.

## Why This Is A Bug

Each request is supposed to produce exactly one access log line, and `use_colors=False` is supposed to mean the output has no terminal escape codes. Because the formatter writes the attacker-controlled decoded path into the line unescaped, anyone who can send a request can forge entries and inject terminal control sequences. This is CWE-117, the issue behind CVE-2020-7694.

## Fix

Re-quote the path before logging it, so that only printable characters get through:

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

The same change is needed in `uvicorn/protocols/utils.py:get_path_with_query_string`, which builds the access-log arguments.

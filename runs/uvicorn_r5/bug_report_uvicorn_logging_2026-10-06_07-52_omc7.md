# Bug Report: uvicorn.logging AccessFormatter allows log injection via percent-encoded CR/LF in the request path

**Target**: `uvicorn.logging.AccessFormatter` (`get_path`, `get_full_path`, `formatMessage`)
**Severity**: High
**Bug Type**: Logic (security: log injection / log forging)
**Date**: 2026-10-06

## Summary

Both HTTP protocol implementations percent-decode the request path before putting it into `scope["path"]` (`h11_impl.py:201` uses `unquote(...)`; `httptools_impl.py:215` uses `urllib.parse.unquote(path)`). `AccessFormatter` then inserts that decoded path into the access log line as-is. A client can send `%0D%0A` in the URL to put raw CR/LF characters into the log. This lets them split one access record into several lines and forge entries that look real.

## Property-Based Test

```python
import logging
from urllib.parse import unquote
from hypothesis import given, settings, strategies as st
from uvicorn.logging import AccessFormatter

def make_record(scope, status):
    rec = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1,
        '%s - "%s %s HTTP/%s" %d', ("", scope["method"], "", "1.1", status), None)
    rec.status_code = status
    rec.scope = scope
    return rec

def scope_from(raw_path, qs, client):
    return {"type": "http", "method": "GET", "http_version": "1.1",
            "path": unquote(raw_path), "root_path": "",
            "query_string": qs.encode("ascii"), "client": client}

query = st.text(alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7e, blacklist_characters="#"))
client = st.one_of(st.none(), st.tuples(st.sampled_from(["127.0.0.1", "::1"]), st.integers(0, 65535)))
pct = st.integers(0, 255).map(lambda b: "%%%02X" % b)
plain = st.characters(min_codepoint=0x21, max_codepoint=0x7e, blacklist_characters="?#%")
raw_target = st.lists(st.one_of(plain, pct)).map(lambda xs: "/" + "".join(xs))

@settings(max_examples=1000)
@given(raw_target, query, client, st.integers(100, 599))
def test_access_log_is_single_line(raw_path, qs, cl, code):
    f = AccessFormatter(fmt='%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False)
    out = f.format(make_record(scope_from(raw_path, qs, cl), code))
    assert "\n" not in out and "\r" not in out, repr(out)
```

**Failing input**: `raw_path='/%0A'` → `'INFO:      - "GET /\n HTTP/1.1" 100 Continue'`

## Reproducing the Bug

```python
import logging
from urllib.parse import unquote
from uvicorn.logging import AccessFormatter

scope = {"method": "GET", "http_version": "1.1", "client": ("127.0.0.1", 5000),
         "path": unquote('/%0D%0AINFO:     127.0.0.1:1 - "GET /admin HTTP/1.1" 200 OK'),
         "query_string": b""}
record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "", (), None)
record.status_code, record.scope = 404, scope
fmt = AccessFormatter('%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False)
print(fmt.format(record))
```

Output (one real 404 request shows up as two log entries, the second forged as a 200):

```
INFO:     127.0.0.1:5000 - "GET /
INFO:     127.0.0.1:1 - "GET /admin HTTP/1.1" 200 OK HTTP/1.1" 404 Not Found
```

## Why This Is A Bug

Uvicorn's access log format (`'%s - "%s %s HTTP/%s" %d'`, and the default `access` formatter in `config.py`) writes one line per request, with the request line in quotes. That is what log parsers, SIEMs, and people reading the log rely on. Any remote client can break this with a percent-encoded path, without being authenticated. They can fake access entries, hide their own requests, or insert terminal escape sequences (`%1B`). This is the issue tracked as CVE-2020-7694.

## Fix

Re-encode the path before logging it, as the upstream fix did. Apply the same change to `uvicorn/protocols/utils.py:get_path_with_query_string`, which builds the message arguments for the default `%(message)s`.

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
+    path_with_query_string = urllib.parse.quote(scope.get("root_path", "") + scope["path"])
```

# Bug Report: wlc.Weblate._should_verify_ssl disables TLS verification for non-localhost hosts

**Target**: `wlc.Weblate._should_verify_ssl` / `wlc.Weblate.invoke_request`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

TLS certificate verification is meant to be skipped only for localhost (`127.0.0.1`), but the check is `urlparse(path).netloc.startswith("127.0.0.1")`. Any remote host whose netloc *starts with* that string, such as `127.0.0.1.attacker.example` or `127.0.0.1@attacker.example`, also gets `verify=False`. The API token is then sent over an unverified TLS connection.

## Property-Based Test

```python
from urllib.parse import urlparse
from hypothesis import assume, given, strategies as st
import wlc

label = st.from_regex(r"[a-z][a-z0-9-]{0,10}[a-z0-9]", fullmatch=True)
domain = st.lists(label, min_size=1, max_size=4).map(".".join)

@given(suffix=st.one_of(domain.map(lambda d: "." + d), st.integers(0, 99).map(str)),
       path=st.from_regex(r"(/[a-z0-9]{0,8}){0,3}", fullmatch=True))
def test_ssl_verified_for_non_localhost(suffix, path):
    url = f"https://127.0.0.1{suffix}{path}"
    assume(urlparse(url).hostname != "127.0.0.1")
    assert wlc.Weblate._should_verify_ssl(url), url
```

**Failing input**: `suffix='0', path=''` → `https://127.0.0.10`. The same failure occurs for `.evil.com`-style suffixes.

## Reproducing the Bug

```python
from unittest import mock
import wlc

assert wlc.Weblate._should_verify_ssl("https://127.0.0.1.evil.com/api/") is False
assert wlc.Weblate._should_verify_ssl("https://127.0.0.1@evil.com/api/") is False

w = wlc.Weblate(key="secret", url="https://127.0.0.1.attacker.example/api/")
with mock.patch.object(w.session, "request") as req:
    req.return_value.status_code = 200
    req.return_value.json.return_value = {}
    w.get("projects/")
print(req.call_args.kwargs["verify"], req.call_args.kwargs["headers"]["Authorization"])
# False Token secret
```

## Why This Is A Bug

The code and its comment ("Disable insecure warnings for localhost") say verification is skipped only for localhost. A prefix match on the raw netloc, which also contains userinfo and port, lets attacker-controlled DNS names and `user@host` URLs skip certificate checks. That makes man-in-the-middle attacks possible and exposes the `Authorization: Token ...` header. The same applies to absolute URLs that the server returns, such as pagination `next` links.

## Fix

```diff
     @staticmethod
     def _should_verify_ssl(path):
         """Checks if it should verify ssl certificates."""
         url = urlparse(path)
-        is_localhost = url.netloc.startswith(LOCALHOST_NETLOC)
+        is_localhost = url.hostname == LOCALHOST_NETLOC
         return url.scheme == "https" and (not is_localhost)
```

# Bug Report: wlc.Weblate._should_verify_ssl Disables TLS verification for non-localhost hosts

**Target**: `wlc.Weblate._should_verify_ssl`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`_should_verify_ssl` is meant to skip certificate verification only for localhost (`127.0.0.1`). It actually checks `url.netloc.startswith("127.0.0.1")`, so any remote hostname that starts with `127.0.0.1` also gets `verify=False`. Examples are `https://127.0.0.1.evil.com/` and `https://127.0.0.10/`. Those requests carry the `Authorization: Token ...` header.

## Property-Based Test

```python
hostnames = st.from_regex(r"\A[a-z][a-z0-9]{0,10}(\.[a-z][a-z0-9]{0,10}){1,3}\Z")


@settings(max_examples=300)
@given(hostnames)
def test_ssl_verified_for_non_localhost(host):
    url = f"https://127.0.0.1.{host}/api/"
    assert wlc.Weblate._should_verify_ssl(url), url
```

**Failing input**: `host='a.a'`, i.e. `https://127.0.0.1.a.a/api/`

## Reproducing the Bug

```python
import wlc

print(wlc.Weblate._should_verify_ssl("https://127.0.0.1.evil.com/api/"))  # False
print(wlc.Weblate._should_verify_ssl("https://127.0.0.10/api/"))          # False
print(wlc.Weblate._should_verify_ssl("https://example.com/api/"))         # True
```

## Why This Is A Bug

The comment in `invoke_request` reads "Disable insecure warnings for localhost". It shows that the only intended exemption is the local machine. A prefix match on `netloc` also exempts public DNS names such as `127.0.0.1.attacker.example`. A network attacker can then MITM HTTPS traffic to such a host without a valid certificate and capture the API token. Because `logging.captureWarnings(True)` is enabled at the same time, the user also gets no InsecureRequestWarning.

## Fix

```diff
--- a/wlc/__init__.py
+++ b/wlc/__init__.py
@@ def _should_verify_ssl(path):
         """Checks if it should verify ssl certificates."""
         url = urlparse(path)
-        is_localhost = url.netloc.startswith(LOCALHOST_NETLOC)
+        is_localhost = url.hostname == LOCALHOST_NETLOC
         return url.scheme == "https" and (not is_localhost)
```

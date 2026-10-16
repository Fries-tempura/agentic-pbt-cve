# Bug Report: wlc.Weblate._should_verify_ssl Turns off TLS verification for hosts that merely start with "127.0.0.1"

**Target**: `wlc.Weblate._should_verify_ssl`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

TLS certificate verification is meant to be skipped only for localhost. The check is `url.netloc.startswith("127.0.0.1")`, so a remote host such as `127.0.0.1.evil.com` (or `127.0.0.10`, or `127.0.0.1@evil.com`) also gets `verify=False`.

## Property-Based Test

```python
@given(st.from_regex(r"[a-z]{1,10}\.(com|org|net)", fullmatch=True))
def test_ssl_verified_for_remote_hosts(domain):
    assert wlc.Weblate._should_verify_ssl(f"https://{domain}/api/")
    assert wlc.Weblate._should_verify_ssl(f"https://127.0.0.1.{domain}/api/")
```

**Failing input**: `domain='a.com'`

## Reproducing the Bug

```python
import wlc
print(wlc.Weblate._should_verify_ssl("https://127.0.0.1.evil.com/api/"))  # False
print(wlc.Weblate._should_verify_ssl("https://127.0.0.1@evil.com/api/"))  # False
```

## Why This Is A Bug

The code comment says "Disable insecure warnings for localhost". A non-local HTTPS server gets no certificate verification, so the API token in the `Authorization` header can be intercepted.

## Fix

```diff
-        is_localhost = url.netloc.startswith(LOCALHOST_NETLOC)
+        is_localhost = url.hostname == LOCALHOST_NETLOC
```

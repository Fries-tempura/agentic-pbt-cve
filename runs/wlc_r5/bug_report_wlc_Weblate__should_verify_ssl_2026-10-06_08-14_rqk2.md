# Bug Report: wlc.Weblate._should_verify_ssl disables TLS verification for hosts starting with "127.0.0.1"

**Target**: `wlc.Weblate._should_verify_ssl`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

The localhost exemption uses `url.netloc.startswith("127.0.0.1")`. Any remote hostname that begins with that string also passes the check, for example `127.0.0.1.attacker.com` or `127.0.0.10`. For those hosts wlc sends HTTPS requests with `verify=False` and the API token in the `Authorization` header.

## Property-Based Test

```python
from hypothesis import given, strategies as st
import wlc

hostlabel = st.from_regex(r"[a-z][a-z0-9]{0,10}", fullmatch=True)

@given(hostlabel, st.sampled_from(["com", "net", "org", "io"]))
def test_ssl_verification_only_skipped_for_localhost(label, tld):
    url = f"https://127.0.0.1.{label}.{tld}/api/"
    assert wlc.Weblate._should_verify_ssl(url)
```

**Failing input**: `label='a', tld='com'`, which gives `https://127.0.0.1.a.com/api/`.

## Reproducing the Bug

```python
import wlc

assert wlc.Weblate._should_verify_ssl("https://127.0.0.1.attacker.com/api/") is False
assert wlc.Weblate._should_verify_ssl("https://127.0.0.10/api/") is False
```

## Why This Is A Bug

The comment in `invoke_request` says the intent is "Disable insecure warnings for localhost". Only the loopback host should be exempt. A prefix match on the netloc also exempts remote hosts. For them, certificate validation is silently turned off, so a man-in-the-middle can intercept the API token and change responses.

## Fix

```diff
--- a/wlc/__init__.py
+++ b/wlc/__init__.py
@@ def _should_verify_ssl(path):
         url = urlparse(path)
-        is_localhost = url.netloc.startswith(LOCALHOST_NETLOC)
+        is_localhost = url.hostname == LOCALHOST_NETLOC
         return url.scheme == "https" and (not is_localhost)
```

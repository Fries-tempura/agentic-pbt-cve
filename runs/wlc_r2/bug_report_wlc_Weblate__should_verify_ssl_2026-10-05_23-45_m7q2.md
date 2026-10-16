# Bug Report: wlc.Weblate._should_verify_ssl Disables TLS Verification for Hosts Starting with "127.0.0.1"

**Target**: `wlc.Weblate._should_verify_ssl`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

The localhost exemption from TLS certificate verification is checked with `url.netloc.startswith("127.0.0.1")`. Any remote hostname that begins with that string, such as `127.0.0.1.attacker.example`, also gets `verify=False`.

## Property-Based Test

```python
hostnames = st.from_regex(r"\A[a-z][a-z0-9-]{0,10}(\.[a-z][a-z0-9-]{0,10}){0,3}\Z")

@given(st.one_of(hostnames, hostnames.map(lambda h: "127.0.0.1." + h),
                 hostnames.map(lambda h: "127.0.0.10" + "." + h)),
       st.sampled_from(["", ":8443"]))
def test_ssl_verify_for_non_localhost(host, port):
    url = f"https://{host}{port}/api/"
    if urllib.parse.urlparse(url).hostname == "127.0.0.1":
        return
    assert wlc.Weblate._should_verify_ssl(url), url
```

**Failing input**: `host='127.0.0.1.a', port=''`

## Reproducing the Bug

```python
import wlc
assert wlc.Weblate._should_verify_ssl("https://127.0.0.1.attacker.example/api/") is False
assert wlc.Weblate._should_verify_ssl("https://127.0.0.10/api/") is False
```

## Why This Is A Bug

The code means to skip certificate checks only for localhost (comment: "Disable insecure warnings for localhost"). Matching on a prefix also exempts real DNS names and other IPs such as `127.0.0.10`. Requests to those hosts, which carry the `Authorization: Token ...` header, go out with no certificate validation, so a man-in-the-middle can steal the API key. The URL is not always one the user configured: `list_factory` follows server-supplied `next` URLs, and absolute URLs are used as-is.

## Fix

```diff
-        is_localhost = url.netloc.startswith(LOCALHOST_NETLOC)
+        is_localhost = url.hostname == LOCALHOST_NETLOC
```

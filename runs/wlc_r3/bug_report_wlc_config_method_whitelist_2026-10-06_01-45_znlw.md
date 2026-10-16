# Bug Report: wlc.config default method_whitelist is parsed as one bogus method

**Target**: `wlc.config.WeblateConfig.get_request_options`
**Severity**: Low
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

The default `method_whitelist` is stored as `"HEAD\nTRACE\nDELETE\nOPTIONS\nPUT\nGET"`, which is newline-separated. `get_request_options` splits it on `","`, so the result is a single string `'HEAD\nTRACE\nDELETE\nOPTIONS\nPUT\nGET'` instead of six HTTP methods.

## Property-Based Test

```python
from wlc.config import WeblateConfig

def test_default_method_whitelist():
    methods = WeblateConfig().get_request_options()[2]
    assert all("\n" not in m for m in methods), methods
```

**Failing input**: the default configuration

## Reproducing the Bug

```python
from wlc.config import WeblateConfig

print(WeblateConfig().get_request_options()[2])
# ['HEAD\nTRACE\nDELETE\nOPTIONS\nPUT\nGET']
```

## Why This Is A Bug

`Retry(allowed_methods=...)` expects a collection of method names. With this value, no method would ever match, so retries would never apply to any method. The bug is currently hidden because of the separate bug where the `Retry` object is never used (see `bug_report_wlc_Weblate_retries_2026-10-06_01-45_zsgz.md`).

## Fix

```diff
-        self.set(
-            self.section, "method_whitelist", "HEAD\nTRACE\nDELETE\nOPTIONS\nPUT\nGET"
-        )
+        self.set(
+            self.section, "method_whitelist", "HEAD,TRACE,DELETE,OPTIONS,PUT,GET"
+        )
```

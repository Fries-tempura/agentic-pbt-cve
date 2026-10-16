# Bug Report: wlc.Weblate ignores the configured retry options

**Target**: `wlc.Weblate.__init__`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`Weblate.__init__` builds a `Retry` object from `retries`, `status_forcelist`, `method_whitelist` and `backoff_factor`, then passes the raw `retries` constructor argument to `HTTPAdapter(max_retries=retries)` instead of that object. Two things follow:
- When the client is built from a config (`config=...`), the `retries` setting is ignored completely, because the argument defaults to `0`.
- `status_forcelist`, `backoff_factor` and `method_whitelist` are never applied.

## Property-Based Test

```python
from hypothesis import given, strategies as st
import wlc
from wlc.config import WeblateConfig

@given(retries=st.integers(1, 20))
def test_retries_applied_from_config(retries):
    c = WeblateConfig()
    c.set("weblate", "retries", str(retries))
    w = wlc.Weblate(config=c)
    assert w.adapter.max_retries.total == retries
```

**Failing input**: `retries=1`

## Reproducing the Bug

```python
import wlc
from wlc.config import WeblateConfig

c = WeblateConfig()
c.set("weblate", "retries", "5")
print(wlc.Weblate(config=c).adapter.max_retries)
# Retry(total=0, ...)

w = wlc.Weblate(retries=3, status_forcelist=[502], backoff_factor=2)
print(w.adapter.max_retries.status_forcelist, w.adapter.max_retries.backoff_factor)
# set() 0
```

## Why This Is A Bug

The constructor docstring says it stores "requests retry args", and the config exposes `retries`, `status_forcelist`, `method_whitelist` and `backoff_factor`. The `Retry` object built from them is assigned to `self.retries` but never used, so user-configured retry behaviour has no effect.

## Fix

```diff
-        self.adapter = HTTPAdapter(pool_connections=1, max_retries=retries)
+        self.adapter = HTTPAdapter(pool_connections=1, max_retries=self.retries)
```

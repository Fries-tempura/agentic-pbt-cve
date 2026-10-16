# Bug Report: lxml_html_clean.clean Cleaner with host_whitelist crashes on malformed bracketed URLs

**Target**: `lxml_html_clean.clean.Cleaner.allow_embedded_url`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-05

## Summary

When `host_whitelist` is set, `Cleaner.clean_html` raises an uncaught `ValueError` if the input HTML has an `<iframe>`/`<embed>` whose `src` contains an unbalanced or invalid bracketed host (for example `http://[`). `allow_embedded_url` calls `urllib.parse.urlsplit` without handling the exception, so a single attacker-controlled attribute can stop sanitization of the whole document.

## Property-Based Test

```python
import warnings
from hypothesis import given, settings, strategies as st
from lxml_html_clean import Cleaner

warnings.simplefilter("ignore")

url_chars = st.sampled_from(list("abcdefghijklmnopqrstuvwxyz0123456789.:/?#@[]\\%-_ \t"))
host_like = st.text(url_chars, max_size=25)


@given(st.sampled_from(["http://", "https://", "//", "https:", ""]), host_like)
@settings(max_examples=1000)
def test_whitelist_clean_never_crashes(prefix, rest):
    cleaner = Cleaner(host_whitelist=["trusted.com"])
    url = prefix + rest
    html = '<div><iframe src="%s"></iframe></div>' % url.replace('"', "")
    cleaner.clean_html(html)  # must not raise
```

**Failing input**: `prefix='http://', rest='['`

## Reproducing the Bug

```python
from lxml_html_clean import Cleaner

cleaner = Cleaner(host_whitelist=["trusted.com"])
cleaner.clean_html('<div><iframe src="http://["></iframe></div>')
# ValueError: Invalid IPv6 URL

cleaner.clean_html('<div><iframe src="https://[evil]/"></iframe></div>')
# ValueError: 'evil' does not appear to be an IPv4 or IPv6 address
```

## Why This Is A Bug

`Cleaner` is meant to sanitize untrusted HTML. An embedded URL that can't be parsed should be treated as not allowed and removed, which is how the code already handles ambiguous URLs (`AmbiguousURLWarning`, `return False`). Instead, the `ValueError` from `urlsplit` propagates out of `clean_html`. Every application that turns on `host_whitelist` (the documented way to allow, for example, YouTube iframes) can then be crashed by user-supplied content. This is a denial of service, and callers that catch exceptions broadly may fall back to unsanitized output. The default cleaner, without `host_whitelist`, doesn't call `urlsplit`, so it accepts the same input without error.

## Fix

```diff
--- a/lxml_html_clean/clean.py
+++ b/lxml_html_clean/clean.py
@@ -533,7 +533,12 @@ class Cleaner:
             return False
         if not self.host_whitelist:
             return False
-        parts = urlsplit(url)
+        try:
+            parts = urlsplit(url)
+            hostname = parts.hostname
+        except ValueError:
+            # Malformed URL (e.g. invalid IPv6 literal): never allow it.
+            return False
         if parts.scheme not in ('http', 'https'):
             return False
 
@@ -544,7 +549,7 @@ class Cleaner:
                           AmbiguousURLWarning)
             return False
 
-        if parts.hostname in self.host_whitelist:
+        if hostname in self.host_whitelist:
             return True
         return False
```

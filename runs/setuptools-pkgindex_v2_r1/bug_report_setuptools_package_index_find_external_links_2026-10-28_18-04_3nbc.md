# Bug Report: setuptools.package_index.find_external_links takes quadratic time on pages with many unclosed `<`

**Target**: `setuptools.package_index.find_external_links` (regex `REL`)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

The `REL` regex, `<([^>]*\srel...)>`, lets `[^>]*` match `<`. On a page with many `<` and no `>`, every `<` scans to the end of the page and backtracks at each whitespace character, so the scan costs O(n²). A 64 KB page of `"< "` takes about 8 s, and a few hundred KB stalls `easy_install`/`PackageIndex` for minutes.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st, HealthCheck
from setuptools.package_index import find_external_links

@settings(max_examples=10, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.sampled_from(["< ", "<\t", "< a", "<a ", "< rel "]))
def test_find_external_links_linear(unit):
    """CLAIM-6: link scanning time is roughly linear in page size."""
    def t(n):
        page = unit * n
        s = time.perf_counter(); list(find_external_links("http://x/", page)); return time.perf_counter() - s
    small, big = t(1500), t(6000)
    assert big < max(small, 1e-3) * 6, (unit, small, big)
```

**Failing input**: `unit='< '` (with 4× the input, the time went up about 15×: 0.019 s → 0.288 s)

## Reproducing the Bug

```python
import time
from setuptools.package_index import find_external_links

for n in (8000, 16000, 32000):
    s = time.time()
    list(find_external_links("http://x/", "< " * n))
    print(2 * n, "bytes:", round(time.time() - s, 2), "s")
```

Output: 16000 bytes: 0.5 s, 32000 bytes: 2.05 s, 64000 bytes: 8.21 s.

## Why This Is A Bug

`find_external_links` runs on every package page that `PackageIndex.process_index` fetches. These are remote, untrusted HTML pages. Scanning a page for links should take time linear in its size. The current `REL` pattern was introduced to fix an earlier ReDoS in this same function (CVE-2022-40897), but it is still quadratic, so a hostile or compromised index or `find_links` page can hang the client.

## Fix

Excluding `<` from the leading class means each attempt stops at the next tag start. Matches on well-formed tags are unchanged; the scan time on the input above drops from 8.3 s to 0.001 s.

```diff
-REL = re.compile(r"""<([^>]*\srel\s{0,10}=\s{0,10}['"]?([^'" >]+)[^>]*)>""", re.I)
+REL = re.compile(r"""<([^<>]*\srel\s{0,10}=\s{0,10}['"]?([^'" >]+)[^>]*)>""", re.I)
```

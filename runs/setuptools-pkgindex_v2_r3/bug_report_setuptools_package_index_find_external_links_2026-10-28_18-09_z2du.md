# Bug Report: setuptools.package_index find_external_links takes quadratic time (ReDoS in REL regex)

**Target**: `setuptools.package_index.find_external_links` (`REL` regex)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`REL = <([^>]*\srel\s{0,10}=...)>` can match `<` inside `[^>]*`. On a page with many `<` and no `>`, every `<` starts a scan to the end of the page, so time grows quadratically. An 80 KB page (`"< " * 40000`) takes about 13 s.

## Property-Based Test

```python
@settings(max_examples=10, deadline=None)
@given(unit=st.sampled_from(["< ", "<a ", "<a rel ", "<\t", "<a href=x "]))
def test_find_external_links_linear(unit):
    """CLAIM-5: find_external_links cost scales roughly linearly with page size."""
    def t(n):
        page = unit * n
        s = time.perf_counter()
        list(find_external_links("http://x/", page))
        return time.perf_counter() - s
    small, big = t(2000), t(16000)
    assert big < max(small, 0.005) * 8 * 4, (unit, small, big)
```

**Failing input**: `unit='< '`. Making the page 8x larger made it 63x slower (0.034 s to 2.1 s).

## Reproducing the Bug

```python
import time
from setuptools.package_index import find_external_links

for n in (5000, 10000, 20000, 40000):
    s = time.perf_counter()
    list(find_external_links("http://x/", "< " * n))
    print(n, round(time.perf_counter() - s, 3))
```

Output: `5000 0.202`, `10000 0.842`, `20000 3.285`, `40000 13.197`. Each doubling of the input takes about 4x as long.

## Why This Is A Bug

`PackageIndex.process_index` calls `find_external_links` on HTML fetched from package index servers, which are untrusted. The time spent should grow linearly with page size. A small malicious page can stall `easy_install`/`PackageIndex` for minutes. CVE-2022-40897 already tried to fix this regex by bounding `\s{0,10}`, but the quadratic case through `[^>]*` is still there.

## Fix

If `[^>]*` cannot cross a `<`, each scan stops at the next tag start and the time becomes linear. Checked: `"< "*40000` takes 0.002 s, and `<a href="x" rel="download">` still matches.

```diff
-REL = re.compile(r"""<([^>]*\srel\s{0,10}=\s{0,10}['"]?([^'" >]+)[^>]*)>""", re.I)
+REL = re.compile(r"""<([^<>]*\srel\s{0,10}=\s{0,10}['"]?([^'" >]+)[^>]*)>""", re.I)
```

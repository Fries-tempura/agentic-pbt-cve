# Bug Report: setuptools.package_index find_external_links takes quadratic time on pages with many `<`

**Target**: `setuptools.package_index.find_external_links` (`REL` regex)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

The `REL` regex `<([^>]*\srel\s{0,10}=...)>` is run with `finditer` over every downloaded index page. On a page with many `<` characters and no `>`, the work grows with the square of the page length. A 64 KB page takes about 15 s; a page of a few MB would hang `easy_install` / `PackageIndex.process_index` for hours.

## Property-Based Test

```python
def _time(page):
    t = time.perf_counter()
    list(find_external_links("http://a/", page))
    return time.perf_counter() - t

@settings(max_examples=5, deadline=None)
@given(st.sampled_from(["<", "< ", "<a "]))
def test_find_external_links_linear(unit):
    """CLAIM-5: scanning a page costs ~linear time in its length."""
    n = 4000
    small = _time(unit * n)
    big = _time(unit * (4 * n))
    # linear => ~4x; quadratic => ~16x
    assert big < max(10 * small, 0.05), (unit, small, big)
```

**Failing input**: `unit='<'` (4,000 chars: 0.073 s; 16,000 chars: 1.02 s)

## Reproducing the Bug

```python
import time
from setuptools.package_index import find_external_links

for n in (16000, 32000, 64000):
    t = time.time()
    list(find_external_links("http://a/", "<" * n))
    print(n, round(time.time() - t, 2))
```

Output: `16000 0.96`, `32000 3.76`, `64000 15.21`. Each doubling of the input makes it about 4× slower.

## Why This Is A Bug

`find_external_links` runs on HTML fetched from package index servers (`process_index`). That HTML is remote input and may be untrusted. At every `<`, `[^>]*` runs to the end of the input and then backtracks while looking for `\srel`. That makes the scan O(n²). The `\s{0,10}` bounds were added earlier to fix ReDoS (CVE-2022-40897), but the unbounded `[^>]*` prefix still makes the scan quadratic.

## Fix

Exclude `<` from the tag body as well, so a failed match cannot run past the next tag start:

```diff
-REL = re.compile(r"""<([^>]*\srel\s{0,10}=\s{0,10}['"]?([^'" >]+)[^>]*)>""", re.I)
+REL = re.compile(r"""<([^<>]*\srel\s{0,10}=\s{0,10}['"]?([^'" ><]+)[^<>]*)>""", re.I)
```

This makes each starting `<` scan only up to the next `<`, so the total work is linear. A more robust option is to parse tags with `html.parser.HTMLParser`.

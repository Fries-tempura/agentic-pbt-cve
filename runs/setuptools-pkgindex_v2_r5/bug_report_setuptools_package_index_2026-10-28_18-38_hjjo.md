# Bug Report: setuptools.package_index REL regex takes cubic time (ReDoS) on fetched pages

**Target**: `setuptools.package_index.find_external_links` (the `REL` regex)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`REL = <([^>]*\srel\s{0,10}=\s{0,10}['"]?([^'" >]+)[^>]*)>` backtracks in cubic time when no `>` follows. `find_external_links` runs it over HTML fetched from a package index. A 12 KB page of `< rel=` repeated takes about 38 s, and each doubling of the size makes it about 8× slower.

## Property-Based Test

```python
@settings(max_examples=20, deadline=None)
@given(st.sampled_from(["< rel=", "<a rel=" + " " * 10, "<x rel", "<" + " rel" * 5]), st.integers(200, 1200))
def test_find_external_links_linear(chunk, n):
    """CLAIM-6: regex scanning of a page is roughly linear."""
    page = chunk * n
    t0 = time.perf_counter()
    list(find_external_links("https://x.org/", page))
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, (chunk, n, elapsed)
```

**Failing input**: `chunk='< rel=', n=595` (a 3.5 KB page took more than 1 s)

## Reproducing the Bug

```python
import time
from setuptools.package_index import find_external_links

for n in (500, 1000, 2000):
    page = '< rel=' * n
    t = time.perf_counter()
    list(find_external_links('https://x.org/', page))
    print(n, round(time.perf_counter() - t, 2))
```

Measured: 500 → 0.6 s, 1000 → 4.8 s, 2000 → 37.7 s. With `'<a rel=          '` as the chunk: 2000 → 212 s.

## Why This Is A Bug

`process_index` calls `find_external_links` on pages downloaded from the network. A malicious or compromised index can stall `easy_install`/`PackageIndex` for hours with a page of a few tens of KB. The work should be linear in the page size. Two things cause the blow-up. First, `[^>]*` can run across `<`, so every `<` restarts a scan to the end of the page. Second, `([^'" >]+)[^>]*` can split the same tail in many ways.

## Fix

Match whole tags with a linear regex, then search for `rel` inside each tag. This gives the same `(tag, rel)` groups on ordinary tags and runs in about 4 ms on the 340 KB inputs that used to hang:

```diff
--- a/setuptools/package_index.py
+++ b/setuptools/package_index.py
-REL = re.compile(r"""<([^>]*\srel\s{0,10}=\s{0,10}['"]?([^'" >]+)[^>]*)>""", re.I)
-"""
-Regex for an HTML tag with 'rel="val"' attributes.
-"""
+TAG = re.compile(r"<([^<>]*)>")
+REL_ATTR = re.compile(r"""\srel\s{0,10}=\s{0,10}['"]?([^'" >]+)""", re.I)
 
 
 @unique_values
 def find_external_links(url, page):
     """Find rel="homepage" and rel="download" links in `page`, yielding URLs"""
 
-    for match in REL.finditer(page):
-        tag, rel = match.groups()
+    for tag_match in TAG.finditer(page):
+        tag = tag_match.group(1)
+        rel_match = REL_ATTR.search(tag)
+        if not rel_match:
+            continue
+        rel = rel_match.group(1)
         rels = set(map(str.strip, rel.lower().split(',')))
```

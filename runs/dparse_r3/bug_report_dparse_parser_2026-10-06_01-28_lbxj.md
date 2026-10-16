# Bug Report: dparse.parser ReDoS in index-server URL parsing

**Target**: `dparse.parser.Parser.parse_index_server` (reached via `dparse.parse` / `RequirementsTXTParser.parse`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`Parser.parse_index_server` matches `-i` / `--index-url` / `--extra-index-url` lines against `URL_REGEX`, a regex with overlapping quantifiers. It backtracks so badly that the run time grows roughly with the cube of the line length. An ~8 KB requirements file made of one crafted `--index-url` line takes about 26 seconds to parse. Any service that runs dparse on untrusted dependency files (for example, a dependency scanner) can be stalled this way, which is a denial of service.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st, HealthCheck
from dparse import parse, filetypes

@settings(max_examples=50, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.lists(st.sampled_from(["https://", "http://", ":", "@", "a", ".", "/"]), min_size=1, max_size=20),
       st.integers(min_value=1, max_value=600))
def test_parse_requirements_index_line_not_quadratic(chunks, reps):
    content = "--index-url " + "".join(chunks) * reps + "\nrequests==2.0\n"
    t = time.perf_counter()
    parse(content, file_type=filetypes.requirements_txt)
    assert time.perf_counter() - t < 2.0, (len(content))
```

**Failing input**: `chunks=['https://'], reps=531`

## Reproducing the Bug

```python
import time
from dparse import parse, filetypes

content = "--index-url " + "https://" * 1000 + "\nrequests==2.0\n"
t = time.perf_counter()
parse(content, file_type=filetypes.requirements_txt)
print(f"{len(content)} bytes parsed in {time.perf_counter() - t:.1f}s")
```

Output: `8027 bytes parsed in 26.0s`. Timings of `parse_index_server` for `"-i " + "https://"*n`: n=64 → 0.007s, n=256 → 0.44s, n=1024 → 26s.

## Why This Is A Bug

Parsing a small text file should take time roughly proportional to its size. dparse is used by tools such as safety to scan dependency files, which are often untrusted (for example, from pull requests). A single line of a few KB makes the parser hang for tens of seconds, and longer lines make it hang for much longer. This is a regular-expression denial of service (ReDoS). The cause is the user:pass part `(?:\S+(?::\S*)?@)?` combined with the nested `(?:[...]-?)*[...]+` host and domain groups. `findall` retries the match from every position, so the backtracking cost adds up across the whole line.

## Fix

The option value is simply the next token after the flag, so no URL validation regex is needed:

```diff
--- a/dparse/parser.py
+++ b/dparse/parser.py
@@ class Parser(object):
     @classmethod
     def parse_index_server(cls, line):
-        matches = URL_REGEX.findall(line)
-        if matches:
-            url = matches[0]
-            return url if url.endswith("/") else url + "/"
+        groups = re.split(pattern=r"[=\s]+", string=line.strip(), maxsplit=100)
+        if len(groups) >= 2:
+            return groups[1] if groups[1].endswith("/") else groups[1] + "/"
         return None
```

With this patch the reproducer above finishes in about 0.0002s. `-i URL`, `--index-url=URL` and `--extra-index-url URL` still return the URL with a trailing `/`.

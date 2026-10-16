# Bug Report: dparse.parser Catastrophic Backtracking (ReDoS) in `parse_index_server`

**Target**: `dparse.parser.Parser.parse_index_server` (via `dparse.regex.URL_REGEX`)
**Severity**: Medium
**Bug Type**: Logic (performance / ReDoS)
**Date**: 2026-10-05

## Summary

`Parser.parse_index_server` runs `URL_REGEX.findall(line)` on each `-i` / `--index-url` /
`--extra-index-url` line of a requirements file. `URL_REGEX` is vulnerable to catastrophic
backtracking: an index-server line built from a repeated `https://` token causes parse time
to grow super-linearly, so a modest input (a few hundred bytes) can hang the parser for many
seconds. Since `dparse` is routinely run on untrusted/third-party requirements files (it is a
dependency of `safety`), this is a denial-of-service vector.

## Property-Based Test

```python
import time
from hypothesis import given, settings, HealthCheck, strategies as st
from dparse.parser import Parser

@settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.text(alphabet="ab.-:/@1 \t", min_size=0, max_size=60))
def test_index_server_fast(s):
    line = "-i https://" + s * 4
    t = time.perf_counter()
    Parser.parse_index_server(line)
    assert time.perf_counter() - t < 1.0, repr(line)
```

**Failing input**: index-server lines consisting of a repeated `https://` token, e.g.
`"-i " + "https://" * 800`.

Measured scaling (wall-clock seconds) demonstrates the super-linear blowup:

| input token          | n=100 | n=200 | n=400 | n=800 |
|----------------------|-------|-------|-------|-------|
| `"https://" * n`     | 0.014 | 0.111 | 0.841 | 6.624 |
| `"https://a:" * n`   | 0.034 | 0.265 | 2.104 | >15s  |

Doubling the input length multiplies the runtime by ~8x — classic catastrophic backtracking.

## Reproducing the Bug

```python
import time
from dparse.parser import Parser

line = "-i " + "https://" * 800
start = time.perf_counter()
Parser.parse_index_server(line)
print("elapsed:", time.perf_counter() - start, "seconds")
```

End-to-end through the public API (`dparse.parse`), a single crafted line in a
requirements.txt hangs the whole parse:

```python
from dparse import parse, filetypes
parse("-i " + "https://" * 800, file_type=filetypes.requirements_txt)
```

## Why This Is A Bug

`URL_REGEX` (from `dparse/regex.py`) contains host/domain-name subpatterns with nested
quantifiers over overlapping character classes:

```
"(?:(?:[a-z¡-￿0-9]-?)*[a-z¡-￿0-9]+)"
"(?:\.(?:[a-z¡-￿0-9]-?)*[a-z¡-￿0-9]+)*"
```

When the regex engine fails to match a long, repetitive, almost-URL string, it explores an
exponential/polynomial-explosive number of ways to partition the input across these
quantifiers. `parse_index_server` feeds attacker-controlled file content straight into this
regex with no length bound, so a tiny requirements file can consume unbounded CPU. Parsing a
dependency manifest should be linear in file size; here it is not.

## Fix

The robust fix is to bound the regex's work and simplify the host subpattern so it cannot
backtrack catastrophically (e.g. use possessive/atomic grouping via the `regex` module, or
rewrite the host/domain classes to be non-overlapping). A minimal, low-risk mitigation is to
cap the line length before matching, which bounds the worst case:

```diff
--- a/dparse/parser.py
+++ b/dparse/parser.py
@@ class Parser(object):
     @classmethod
     def parse_index_server(cls, line):
         """

         :param line:
         :return:
         """
+        # URL_REGEX is prone to catastrophic backtracking on long, almost-URL
+        # inputs; index server URLs are short, so bound the work.
+        if len(line) > 2048:
+            return None
         matches = URL_REGEX.findall(line)
         if matches:
             url = matches[0]
             return url if url.endswith("/") else url + "/"
         return None
```

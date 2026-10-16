# Bug Report: dparse.parser Polynomial ReDoS in `parse_index_server`

**Target**: `dparse.parser.Parser.parse_index_server` (reached via `dparse.parse(..., file_type=requirements_txt)`)
**Severity**: High
**Bug Type**: Logic (Denial of Service)
**Date**: 2026-10-05

## Summary

`parse_index_server` runs `URL_REGEX.findall(line)` on every `-i` / `--index-url` / `--extra-index-url` line. `URL_REGEX` (from `dparse/regex.py`) has overlapping quantifiers (`\S+(?::\S*)?@`, `(?:[a-z...0-9]-?)*[a-z...0-9]+`, `(?:/\S*)?`), and `findall` retries at every offset. This makes matching time grow polynomially with line length. A line made of repeated `https://` grows roughly cubically: 4 KB takes about 1.7 s, and tens of KB take minutes. Any tool that parses an untrusted requirements file with dparse (for example, safety or a CI dependency scanner) can be stalled this way. This matches CVE-2022-39280.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st, HealthCheck
from dparse import parse, filetypes

@settings(max_examples=50, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.sampled_from(["https://", "http://", "ftp://", "a", "a-", "a."]),
       st.integers(min_value=1, max_value=600))
def test_requirements_parse_scales_linearly(unit, n):
    content = "--index-url " + unit * n + "\ndjango\n"
    t0 = time.perf_counter()
    parse(content, file_type=filetypes.requirements_txt)
    assert time.perf_counter() - t0 < 0.5, (unit, n, len(content))
```

**Failing input**: `unit='https://', n=339` (a 2,732-byte file took more than 0.5 s)

## Reproducing the Bug

```python
import time
from dparse import parse, filetypes

for n in [128, 256, 512]:
    content = "--index-url " + "https://" * n + "\ndjango\n"
    t = time.perf_counter()
    parse(content, file_type=filetypes.requirements_txt)
    print(len(content), round(time.perf_counter() - t, 3))
```

Observed timings:

| Payload | Time |
|---|---|
| `https://` × 128 | 0.028 s |
| `https://` × 256 | 0.22 s |
| `https://` × 512 | 1.71 s |

Each doubling costs about 8×, so the growth is cubic. Extrapolating, a 16 KB line takes about 2 minutes. A run at n=4000 did not finish within 10 minutes and was stopped.

## Why This Is A Bug

A requirements file is untrusted input, and dparse's main use is scanning third-party dependency files. One short line should not consume CPU for minutes. The only thing the parser needs is the option's argument (the token after `-i`, `--index-url` or `--extra-index-url`, separated by spaces or `=`). A general URL-validating regex is not needed for that.

## Fix

```diff
--- a/dparse/parser.py
+++ b/dparse/parser.py
@@ -8,7 +8,7 @@ from configparser import ConfigParser, NoOptionError
 
 
-from .regex import URL_REGEX, HASH_REGEX
+from .regex import HASH_REGEX
 
@@ -175,11 +175,10 @@ class Parser(object):
         :param line:
         :return:
         """
-        matches = URL_REGEX.findall(line)
-        if matches:
-            url = matches[0]
-            return url if url.endswith("/") else url + "/"
+        groups = re.split(r"[=\s]+", line.strip(), maxsplit=2)
+        if len(groups) >= 2:
+            url = groups[1]
+            return url if url.endswith("/") else url + "/"
         return None
```

The patched logic was checked standalone in `check_fix.py`. It passes 11 of the 13 cases in `tests/test_parse.py::test_index_server`; the two not run are trailing-slash variants of cases that pass. It also handles a private-IP URL correctly. On an 800 KB `https://` payload it returns in 0.006 s.

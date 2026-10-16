# Bug Report: dparse.parser Polynomial ReDoS when parsing index-server lines

**Target**: `dparse.parser.Parser.parse_index_server` (reached via `dparse.parse` / `RequirementsTXTParser.parse`)
**Severity**: High
**Bug Type**: Logic (Denial of Service)
**Date**: 2026-10-06

## Summary

`RequirementsTXTParser.parse` sends every `-i` / `--index-url` / `--extra-index-url` line to `Parser.parse_index_server`. That method runs `URL_REGEX.findall(line)`. `URL_REGEX` has overlapping quantifiers (`\S+(?::\S*)?@` and the nested hostname groups), and `findall` retries the match from every position. A crafted line made of repeated URL schemes therefore takes roughly cubic time. A requirements file of a few KB can stall any tool that uses dparse, such as safety or pyup, for seconds to minutes.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st, HealthCheck
from dparse import parse, filetypes

@settings(max_examples=100, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.builds(lambda a, b: a + b, st.sampled_from(["http://", "https://", "ftp://"]),
                 st.text(alphabet="a:@.-1/", max_size=4)), st.integers(100, 800))
def test_index_server_line_bounded_time(unit, reps):
    line = "--index-url " + unit * reps
    t = time.time()
    parse(line + "\nrequests==2.0\n", file_type=filetypes.requirements_txt)
    assert time.time() - t < 2.0, (unit, reps, len(line))
```

**Failing input**: `unit='http://11:', reps=398` (a single line of 3,992 characters)

## Reproducing the Bug

```python
import time
from dparse import parse, filetypes

for n in (200, 400, 800):
    content = "--index-url " + "https://" * n + "\nrequests==2.0\n"
    t = time.time()
    parse(content, file_type=filetypes.requirements_txt)
    print(n, len(content), f"{time.time() - t:.2f}s")
```

Observed output:

```
200 1627 0.11s
400 3227 0.85s
800 6427 6.66s
```

Each doubling of the input makes parsing about 8× slower (cubic growth). A line of about 13 KB takes about a minute, and about 26 KB takes several minutes.

## Why This Is A Bug

dparse exists to parse dependency files from untrusted repositories, for example in vulnerability scanners and CI bots. Parsing a single short line should take linear time. Instead, an attacker-controlled requirements file can hang the parser and deny service to its consumers. This is CVE-2022-39280. The regex search is also unnecessary, because pip's syntax always puts the URL in the token right after the option name.

## Fix

Take the token after the option, split on `=` or whitespace, instead of searching with the URL regex. This keeps every case in the existing `tests/test_parse.py::test_index_server` passing, including inline comments and `=` separators. A 40 KB line now takes under 1 ms.

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
-        matches = URL_REGEX.findall(line)
-        if matches:
-            url = matches[0]
-            return url if url.endswith("/") else url + "/"
+        groups = re.split(r"[=\s]+", line.strip(), maxsplit=100)
+        if len(groups) >= 2:
+            value = groups[1]
+            return value if value.endswith("/") else value + "/"
         return None
```

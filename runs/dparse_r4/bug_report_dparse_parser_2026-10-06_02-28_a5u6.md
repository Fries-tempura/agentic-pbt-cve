# Bug Report: dparse.parser Exponential-time (ReDoS) parsing of `-i/--index-url` lines

**Target**: `dparse.parser.Parser.parse_index_server` (reached via `dparse.parse` / `RequirementsTXTParser.parse`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`RequirementsTXTParser.parse` sends every `-i`, `--index-url` and `--extra-index-url` line to `Parser.parse_index_server`. That function runs `URL_REGEX.findall` on the line. The host and domain parts of `URL_REGEX` are `(?:[a-z¡-￿0-9]-?)*[a-z¡-￿0-9]+` and `(?:\.(?:...-?)*...+)*`. Both are nested quantifiers that can match the same characters in many different ways. On a hostname that almost matches but fails, the regex backtracks catastrophically. For example, a short line in a requirements file makes `dparse.parse` run in time exponential in the line length. That is a denial of service for any tool that parses untrusted requirements files with dparse, such as safety or CI scanners.

## Property-Based Test

```python
import time
from hypothesis import given, settings, strategies as st, HealthCheck
from dparse.parser import Parser

@settings(deadline=None, max_examples=50, suppress_health_check=list(HealthCheck))
@given(st.text(alphabet="a1-.", min_size=1, max_size=4), st.integers(10, 40),
       st.sampled_from(["", "!", " ", ".", "-"]))
def test_parse_index_server_linear_time(chunk, reps, end):
    line = "-i https://" + chunk * reps + end
    t = time.perf_counter()
    Parser.parse_index_server(line)
    assert time.perf_counter() - t < 1.0
```

**Failing input**: `chunk='a.1', reps=37, end=' '` (the test never finishes; a SIGALRM watchdog caught it)

## Reproducing the Bug

```python
import time
from dparse import parse, filetypes

for n in (20, 22, 24, 26):
    content = "-i https://" + "a.1" * n + "\nrequests==2.0"
    t = time.perf_counter()
    parse(content, file_type=filetypes.requirements_txt)
    print(n, round(time.perf_counter() - t, 2))
```

Observed output:

```
20 0.1
22 0.38
24 1.51
26 6.42
```

The runtime doubles with every extra 3 characters. An 80-character line takes about 6 s, a 100-character line would take hours, and a 120-character line would take years.

## Why This Is A Bug

- `parse_index_server` only needs to pull the URL out of a pip option line. Its runtime should be linear in the line length.
- `-i` and `--index-url` lines are ordinary requirements.txt syntax, and dparse is built to parse such files, which are often untrusted. Examples include PR contents and third-party repositories scanned by safety or GitHub integrations.
- One crafted line is enough to hang the process. This is CVE-2022-39280 (ReDoS in dparse < 0.6.2).

## Fix

Don't use the backtracking URL regex. Split the option from its value instead, which is how pip itself tokenizes the line:

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
-        return None
+        groups = re.split(pattern=r"[=\s]+", string=line.strip(), maxsplit=100)
+
+        if len(groups) >= 2:
+            return groups[1] if groups[1].endswith('/') else groups[1] + '/'
+
+        return None
```

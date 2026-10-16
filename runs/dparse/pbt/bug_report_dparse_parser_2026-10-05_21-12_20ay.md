# Bug Report: dparse.parser Private-network index servers are silently dropped

**Target**: `dparse.parser.Parser.parse_index_server`
**Severity**: Low
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`RequirementsTXTParser.parse` calls `parse_index_server` when "this file is using a private index server". However, `URL_REGEX` (taken from a gist that validates public URLs) explicitly rejects private and loopback addresses (10/8, 127/8, 169.254/16, 192.168/16, 172.16/12). It also rejects hostnames with no TLD, such as `localhost`. For these private index servers, `parse_index_server` returns `None`, so every dependency ends up with `index_server = None` and nothing reports the problem.

## Property-Based Test

```python
from hypothesis import given, strategies as st
from dparse.parser import Parser

@given(st.sampled_from(["10.0.0.5", "192.168.1.10", "127.0.0.1", "172.16.0.3"]),
       st.sampled_from(["", ":8080"]))
def test_index_server_private_ip(ip, port):
    url = f"http://{ip}{port}/simple/"
    assert Parser.parse_index_server("-i " + url) == url
```

**Failing input**: `ip='10.0.0.5', port=''` (it fails for every generated value)

## Reproducing the Bug

```python
from dparse import parse, filetypes

dep = parse("-i http://10.0.0.5/simple/\ndjango", file_type=filetypes.requirements_txt).dependencies[0]
assert dep.index_server == "http://10.0.0.5/simple/", dep.index_server
```

## Why This Is A Bug

The code comment says index-server lines indicate a "private index server", and self-hosted indexes on RFC 1918 addresses are common. For `-i https://some.foo/`, the function returns the argument with a trailing slash added. For an equally valid `-i http://10.0.0.5/simple/` it returns `None`, which is inconsistent.

## Fix

The fix in the companion ReDoS report (`bug_report_dparse_parser_2026-10-05_21-12_mz6a.md`) also fixes this. That fix returns the option's argument directly instead of filtering it through `URL_REGEX`.

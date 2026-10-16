# Bug Report: eml_parser.parser `ignore_bad_start` corrupts every email by dropping newlines

**Target**: `eml_parser.parser.EmlParser.decode_email_bytes`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

When `ignore_bad_start=True` is set, `decode_email_bytes` rebuilds the message with `_eml_file += line` after splitting on `b'\n'`. That drops every newline, so all headers and the body get merged into one header line. The guard `b':' not in eml_file.split(b'\n', 1)` checks list membership, not substring membership, so it is almost always true. The corruption therefore affects every input, including well-formed emails, and the feature can't actually recover a file with a bad start.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from eml_parser.parser import EmlParser

hname = st.sampled_from(['Subject', 'From', 'To', 'X-Foo'])
hval = st.text(st.characters(min_codepoint=0x21, max_codepoint=0x7e, blacklist_characters=':'), min_size=1, max_size=20)

@settings(max_examples=200)
@given(st.lists(st.tuples(hname, hval), min_size=1, max_size=5), st.text(st.characters(min_codepoint=0x20, max_codepoint=0x7e), max_size=50))
def test_ignore_bad_start_noop_on_valid(headers, body):
    raw = ''.join(f'{k}: {v}\n' for k, v in headers) + '\n' + body + '\n'
    p = EmlParser(include_raw_body=True)
    a = p.decode_email_bytes(raw.encode())
    b = p.decode_email_bytes(raw.encode(), ignore_bad_start=True)
    assert a['header']['header'] == b['header']['header']
    assert [x['content'] for x in a['body']] == [x['content'] for x in b['body']]
```

**Failing input**: `headers=[('Subject', '0')], body='0'` → `{'subject': ['0']} != {'subject': ['00']}`

## Reproducing the Bug

```python
from eml_parser.parser import EmlParser

p = EmlParser(include_raw_body=True)
raw = b"Subject: hello\nTo: bob@example.com\n\nbody text\n"
print(p.decode_email_bytes(raw)['header']['header'])
print(p.decode_email_bytes(raw, ignore_bad_start=True)['header']['header'])

bad = b"garbage line\nSubject: hi\nTo: bob@example.com\n\nbody\n"
r = p.decode_email_bytes(bad, ignore_bad_start=True)
print(r['header']['header'], r['header']['to'])
```

Output:
```
{'subject': ['hello'], 'to': ['bob@example.com']}
{'subject': ['helloTo: bob@example.combody text']}
{'subject': ['hiTo: bob@example.combody']} []
```

## Why This Is A Bug

The documented purpose of `ignore_bad_start` is to skip leading junk before the headers. Instead it removes all line breaks, so the parser sees one long header line. The `To` recipients, other headers, the body, attachments and extracted IOCs (URLs, emails, IPs) are silently lost. This happens for well-formed input too. Users who enable this option, whether through the constructor or per call, get silently corrupted analysis results.

## Fix

```diff
--- a/eml_parser/parser.py
+++ b/eml_parser/parser.py
@@ -226,15 +226,15 @@
             # Note that this has a considerable performance impact, which is why it is disabled by default.
             _eml_file = b''
 
-            if b':' not in eml_file.split(b'\n', 1):
+            if b':' not in eml_file.split(b'\n', 1)[0]:
                 start = True
-                for line in eml_file.split(b'\n'):
+                for line in eml_file.splitlines(keepends=True):
                     if start and b':' not in line:
                         continue
 
                     start = False
 
                     _eml_file += line
             else:
                 _eml_file = eml_file
```

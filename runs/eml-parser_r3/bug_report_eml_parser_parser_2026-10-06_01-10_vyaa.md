# Bug Report: eml_parser.parser `ignore_bad_start` corrupts every e-mail

**Target**: `eml_parser.parser.EmlParser.decode_email_bytes`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

When `ignore_bad_start=True` is set (in the constructor or per call), `decode_email_bytes` joins the message lines back together without `\n`. Every header then collapses into one line, so `To`, `Subject`, `Date` and the body are lost. This happens for valid e-mails and also for the case the option is meant to handle: an e-mail with junk lines before the headers.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from eml_parser.parser import EmlParser

hdr_val = st.text(st.characters(min_codepoint=32, max_codepoint=126), max_size=30).map(str.strip)
words = st.text(st.sampled_from("abcdefg .,:/@<>\n"), max_size=200)

@settings(max_examples=300)
@given(hdr_val, words)
def test_ignore_bad_start_noop_on_valid_email(subject, body):
    raw = (f"From: alice@example.com\nTo: bob@example.org\nSubject: {subject}\n"
           f"Date: Mon, 1 Jan 2024 10:00:00 +0000\n\n{body}").encode()
    p = EmlParser(include_raw_body=True)
    a = p.decode_email_bytes(raw)
    b = p.decode_email_bytes(raw, ignore_bad_start=True)
    assert a["header"]["subject"] == b["header"]["subject"]
    assert a["header"]["to"] == b["header"]["to"]
    assert a["header"]["from"] == b["header"]["from"]
```

**Failing input**: `subject='', body=''` (`to`: `['bob@example.org']` vs `[]`), also `subject='0'` (`'0'` vs `''`)

## Reproducing the Bug

```python
from eml_parser import EmlParser

p = EmlParser()
raw = b"garbage line\nFrom: alice@example.com\nTo: bob@example.org\nSubject: hello\n\nbody\n"
r = p.decode_email_bytes(raw, ignore_bad_start=True)
print(r["header"]["to"], repr(r["header"]["subject"]), r["header"]["header"])
# [] '' {'from': ['alice@example.comTo, <>']}
```

## Why This Is A Bug

The option is documented as "Ignore invalid file start". It should only drop leading lines that are not headers. The code has two problems:

1. `b':' not in eml_file.split(b'\n', 1)` checks whether some *list element* equals `b':'`, not whether the first line contains a colon. That is almost always true, so the stripping branch runs for every input, including valid e-mails.
2. Inside that branch, `_eml_file += line` adds the kept lines back without their `\n` separators. All headers and the body end up on one line, so the parsed result is wrong without any error being raised.

As a result, any user who turns on `ignore_bad_start` gets wrong output (lost recipients, subject, date and body) for every message. This affects data collection and security analysis that depend on these fields.

## Fix

```diff
--- a/eml_parser/parser.py
+++ b/eml_parser/parser.py
@@ -224,19 +224,13 @@
         if self.ignore_bad_start or ignore_bad_start:
             # Skip invalid start of file
             # Note that this has a considerable performance impact, which is why it is disabled by default.
             _eml_file = b''
 
-            if b':' not in eml_file.split(b'\n', 1):
-                start = True
-                for line in eml_file.split(b'\n'):
-                    if start and b':' not in line:
-                        continue
-
-                    start = False
-
-                    _eml_file += line
-            else:
-                _eml_file = eml_file
+            lines = eml_file.split(b'\n')
+            for i, line in enumerate(lines):
+                if b':' in line:
+                    _eml_file = b'\n'.join(lines[i:])
+                    break
         else:
             _eml_file = eml_file
```

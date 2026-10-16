# Bug Report: eml_parser.parser `ignore_bad_start=True` mangles every e-mail

**Target**: `eml_parser.parser.EmlParser.decode_email_bytes`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

With `ignore_bad_start=True` (constructor or per-call), `decode_email_bytes` joins every line of the input together **with no newline separators**. Because of a second bug on the guard condition, this happens for practically every input, including perfectly valid e-mails. All headers collapse into one corrupted `From` header, and subject, recipients and body are lost.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st, HealthCheck
import eml_parser.parser as P

word = st.from_regex(r"[A-Za-z0-9]{1,12}", fullmatch=True)

@settings(max_examples=200, suppress_health_check=list(HealthCheck))
@given(word, st.lists(st.from_regex(r"[a-z ]{1,20}", fullmatch=True), min_size=0, max_size=3))
def test_ignore_bad_start_strips_only_garbage(subject, garbage):
    good = f"From: a@b.com\nTo: c@d.org\nSubject: {subject}\n\nhello body\n".encode()
    raw = b"".join(g.encode() + b"\n" for g in garbage) + good
    ref = P.EmlParser().decode_email_bytes(good)
    res = P.EmlParser().decode_email_bytes(raw, ignore_bad_start=True)
    assert res["header"]["subject"] == ref["header"]["subject"]
    assert res["header"].get("to") == ref["header"].get("to")
```

**Failing input**: `subject='0', garbage=[]` (no garbage at all; the input is a valid e-mail)

## Reproducing the Bug

```python
import eml_parser

raw = b"From: a@b.com\nTo: c@d.org\nSubject: hi\n\nhello body\n"
p = eml_parser.EmlParser()
print(p.decode_email_bytes(raw)["header"]["subject"])
r = p.decode_email_bytes(raw, ignore_bad_start=True)
print(repr(r["header"]["subject"]), r["header"]["to"], r["header"]["header"])
```

Output:
```
hi
'' [] {'from': ['a@b.comTo, <>']}
```

## Why This Is A Bug

The docstring says `ignore_bad_start` should *"Ignore invalid file start"*, which means skipping leading junk lines before the first header. Instead:
1. `b':' not in eml_file.split(b'\n', 1)` checks whether the bytes object `b':'` is an element of a list of lines, not whether the first line contains a colon. So it is almost always `True`, and the rewrite path runs even for valid input.
2. In the rewrite loop, `_eml_file += line` drops the `\n` that `split` removed, so every header and the body get fused onto one line.

As a result, any user who turns on this option gets corrupted output for every message. Subjects, recipients, body URLs and attachments silently disappear.

## Fix

```diff
-            if b':' not in eml_file.split(b'\n', 1):
+            if b':' not in eml_file.split(b'\n', 1)[0]:
                 start = True
-                for line in eml_file.split(b'\n'):
+                lines = []
+                for line in eml_file.split(b'\n'):
                     if start and b':' not in line:
                         continue
 
                     start = False
 
-                    _eml_file += line
+                    lines.append(line)
+                _eml_file = b'\n'.join(lines)
             else:
                 _eml_file = eml_file
```

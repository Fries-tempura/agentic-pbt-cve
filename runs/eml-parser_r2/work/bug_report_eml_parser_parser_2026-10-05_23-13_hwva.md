# Bug Report: eml_parser.parser `ignore_bad_start` corrupts every e-mail

**Target**: `eml_parser.parser.EmlParser.decode_email_bytes` (`ignore_bad_start=True`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

When `ignore_bad_start` is enabled, `decode_email_bytes` joins the input lines back together without their `\n` separators. This merges all headers and the body into one line. The returned From, To, Subject and body are wrong, and this happens even for perfectly valid e-mails.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from eml_parser.parser import EmlParser

addr = st.from_regex(r"[a-z]{1,8}@[a-z]{1,8}\.(com|org|net)", fullmatch=True)

@settings(max_examples=300)
@given(addr, addr, st.text(alphabet="abcdef ", min_size=1, max_size=20))
def test_ignore_bad_start_on_valid_email(frm, to, subj):
    raw = f"From: {frm}\nTo: {to}\nSubject: {subj.strip() or 'x'}\n\nhello body\n".encode()
    a = EmlParser().decode_email_bytes(raw)
    b = EmlParser().decode_email_bytes(raw, ignore_bad_start=True)
    assert a['header']['from'] == b['header']['from']
    assert a['header']['to'] == b['header']['to']
    assert a['header']['subject'] == b['header']['subject']
```

**Failing input**: `frm='a@a.com', to='a@a.com', subj='a'`

## Reproducing the Bug

```python
from eml_parser.parser import EmlParser

raw = b'From: a@b.com\nTo: c@d.org\nSubject: hi\n\nhello body\n'
r = EmlParser().decode_email_bytes(raw, ignore_bad_start=True)
print(r['header']['from'], r['header']['to'], repr(r['header']['subject']))
# a@b.comto [] ''        (expected: a@b.com ['c@d.org'] 'hi')

raw = b'garbage line\nFrom: a@b.com\nTo: c@d.org\nSubject: hi\n\nhello body\n'
r = EmlParser().decode_email_bytes(raw, ignore_bad_start=True)
print(r['header']['from'], r['header']['to'], repr(r['header']['subject']))
# a@b.comto [] ''
```

## Why This Is A Bug

The docstring says `ignore_bad_start` should "Ignore invalid file start", which means it should skip leading lines that contain no `:`. The code has two problems:

1. `_eml_file += line` adds each line back without its `b'\n'`. All headers end up on one line, the To and Subject headers are lost, and the From value gets corrupted (`a@b.comto`). The body is lost too.
2. `b':' not in eml_file.split(b'\n', 1)` checks whether one of the list's elements equals `b':'`. It does not check whether the first line contains a colon. So this condition is almost always true, and valid e-mails also go through the broken path.

So turning on the option corrupts every e-mail, including the malformed ones it was meant to help with.

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

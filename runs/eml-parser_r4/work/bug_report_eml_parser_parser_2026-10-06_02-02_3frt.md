# Bug Report: eml_parser.parser `email_force_tld=True` leaks into every other EmlParser instance

**Target**: `eml_parser.parser.EmlParser.__init__`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

Creating an `EmlParser(email_force_tld=True)` overwrites the module-global `eml_parser.regexes.email_regex`. After that, every `EmlParser` instance in the process behaves as if `email_force_tld=True`, including ones created later with the default `False`. They silently stop reporting addresses like `john@doe`.

## Property-Based Test

```python
import eml_parser.parser as P
import eml_parser.regexes as R

def test_force_tld_global_state():
    orig = R.email_regex
    body = b"From: a@b.com\nSubject: s\n\nwrite to john@doe please\n"
    before = P.EmlParser(include_raw_body=True).decode_email_bytes(body)['body'][0].get('email')
    P.EmlParser(email_force_tld=True)
    after = P.EmlParser(include_raw_body=True).decode_email_bytes(body)['body'][0].get('email')
    R.email_regex = orig
    assert before == after, (before, after)
```

**Failing input**: `before=['john@doe'], after=None`

## Reproducing the Bug

```python
import eml_parser

raw = b"From: a@b.com\nSubject: s\n\nwrite to john@doe please\n"
print(eml_parser.EmlParser(include_raw_body=True).decode_email_bytes(raw)['body'][0].get('email'))
eml_parser.EmlParser(email_force_tld=True)
print(eml_parser.EmlParser(include_raw_body=True).decode_email_bytes(raw)['body'][0].get('email'))
```

Output: `['john@doe']`, then `None`.

## Why This Is A Bug

`email_force_tld` is documented as a per-instance option (*"By default this is disabled"*). Because it changes module-global state, one parser's configuration affects every other parser in the process, and the change can never be undone (passing `False` later does not restore the regex). This silently changes extraction results in long-running services that use parsers with different settings.

## Fix

Store the regex on the instance and use it everywhere `eml_parser.regexes.email_regex` is used in `parser.py` (`parse_email`, and `CustomPolicy` if needed):

```diff
-        if self.email_force_tld:
-            eml_parser.regexes.email_regex = eml_parser.regexes.email_force_tld_regex
+        self.email_regex = eml_parser.regexes.email_force_tld_regex if self.email_force_tld else eml_parser.regexes.email_regex
```
and replace `eml_parser.regexes.email_regex.` with `self.email_regex.` inside `EmlParser` methods.

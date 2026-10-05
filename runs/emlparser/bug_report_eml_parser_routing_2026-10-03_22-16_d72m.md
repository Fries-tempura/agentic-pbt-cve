# Bug Report: eml_parser.routing.parserouting raises KeyError('from') on Received headers whose comment contains " from "

**Target**: `eml_parser.routing.parserouting`
**Severity**: Medium
**Bug Type**: Crash
**Date**: 2026-10-03

## Summary

`parserouting()` detects the `from`/`by`/`with`/`for` clause borders on a *paren-stripped* copy of the
line (`npline`) but applies the generated regex to the *original* line. When a parenthesised comment
appearing after a `for ` clause contains the substring `" from "` (e.g. qmail's
`(qmail 21481 invoked from network)`), the "From in for field" fixup at `routing.py:173` reads
`out['from']`, which was never populated because no `from ` clause existed outside the parentheses —
raising `KeyError: 'from'`. The exception escapes `EmlParser.parse_email()` (which only guards this
block with `except TypeError`, `parser.py:410`) and aborts parsing of the whole message.

## Property-Based Test

```python
import eml_parser.routing as routing
from hypothesis import given, settings
from hypothesis import strategies as st

HOSTS = st.sampled_from(['mail.example.com', 'smtp.example.org', '10.0.0.1',
                         '[192.168.1.2]', 'localhost', 'mx1.gov.lu'])
ADDRS = st.sampled_from(['alice@example.com', 'bob@example.org', '<carol@example.net>'])
DATES = st.sampled_from(['; Mon, 1 Jan 2024 10:00:00 +0100',
                         '; Tue, 2 Feb 2021 23:59:59 -0500 (CET)', ''])
COMMENTS = st.sampled_from(['(helo=mail.example.com)', '(mail.example.com [10.0.0.1])',
                            '(from userid 500)', '(qmail 21481 invoked from network)',
                            '(user bob authenticated from 10.0.0.1)',
                            '(envelope-from alice@example.com)', ''])


@st.composite
def received_lines(draw):
    parts = []
    if draw(st.booleans()):
        parts.append('from ' + draw(HOSTS))
        parts.append(draw(COMMENTS))
    if draw(st.booleans()):
        parts.append('by ' + draw(HOSTS))
        parts.append(draw(COMMENTS))
    if draw(st.booleans()):
        parts.append('with ' + draw(st.sampled_from(['ESMTP', 'ESMTPS id ABC123', 'SMTP'])))
    if draw(st.booleans()):
        parts.append('for ' + draw(ADDRS))
        parts.append(draw(COMMENTS))
    return ' '.join((' '.join(p for p in parts if p) + draw(DATES)).split())


@settings(max_examples=2000)
@given(received_lines())
def test_parserouting_never_crashes(line):
    out = routing.parserouting(line)
    assert isinstance(out, dict)
    assert out['src'] == line
```

**Failing input**: `'for alice@example.com (qmail 21481 invoked from network); Mon, 1 Jan 2024 10:00:00 +0100'`

## Reproducing the Bug

```python
import eml_parser
import eml_parser.routing

eml_parser.routing.parserouting(
    'for alice@example.com (qmail 21481 invoked from network); Mon, 1 Jan 2024 10:00:00 +0100'
)
```

End-to-end via the public API:

```python
import eml_parser

raw = (
    b'Received: by mail.example.net\r\n'
    b' for alice@example.com (qmail 21481 invoked from network);'
    b' Mon, 1 Jan 2024 10:00:00 +0100\r\n'
    b'From: bob@example.org\r\n'
    b'Subject: test\r\n'
    b'\r\n'
    b'body\r\n'
)

eml_parser.EmlParser().decode_email_bytes(raw)
```

Both raise:

```
File ".../eml_parser/routing.py", line 173, in parserouting
    out['from'] = f"""{out['from']} {' '.join(temp[1:])}"""
                       ~~~^^^^^^^^
KeyError: 'from'
```

## Why This Is A Bug

* The docstring states the function "tries to parse an e-mail header received line" across "a large
  number of formats" and *returns a dict*; for unparsable input it is designed to return a `warning`
  key rather than raise (see the `Nothing Parsable` / `Merged Received headers` branches).
* The comment on line 169 (`include spaces in test, otherwise there will be an exception with domains
  containing "from" in itself`) shows the author intended this branch to be exception-free.
* Received headers are fully attacker-controlled untrusted input — this is the exact data the library
  exists to parse. `parse_email()` only catches `TypeError` around this block, so the `KeyError`
  propagates out of `decode_email_bytes()` / `decode_email()` and the entire message fails to parse.
  Any consumer scanning mail (the library's stated use case) can be made to crash by a one-line
  header such as `Received: by h for a@b.c (qmail 1 invoked from network);`.

The root cause is the mismatch between the border scan (done on `npline`, with parentheses and the
date removed) and the regex application (done on `line`, with parentheses intact), so the `for`
capture group can contain text that the border scan never saw.

## Fix

Only merge into `out['from']` when that key actually exists; otherwise create it from the split
remainder.

```diff
--- a/eml_parser/routing.py
+++ b/eml_parser/routing.py
@@ -168,10 +168,13 @@ def parserouting(line: str) -> dict[str, typing.Any]:
     if out.get('for'):
         # include spaces in test, otherwise there will be an exception with domains containing "from" in itself
         if ' from ' in out.get('for', ''):
             temp = re.split(' from ', out['for'])
             out['for'] = temp[0]
-            out['from'] = f"""{out['from']} {' '.join(temp[1:])}"""
+            tail = ' '.join(temp[1:])
+            if out.get('from'):
+                out['from'] = f"""{out['from']} {tail}"""
+            else:
+                out['from'] = tail
 
         m = eml_parser.regexes.email_regex.findall(out['for'])
         if m:
```

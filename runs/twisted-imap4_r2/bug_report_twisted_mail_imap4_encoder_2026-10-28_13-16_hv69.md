# Bug Report: twisted.mail.imap4 modified UTF-7 codec drops TAB/CR/LF

**Target**: `twisted.mail.imap4.encoder` / `modified_base64` (codec `imap4-utf-7`)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

The `imap4-utf-7` encoder silently loses `\t`, `\r` and `\n` (or leaves them raw in its output). `"\r".encode("imap4-utf-7")` returns `b"&-"`, which decodes to `"&"`. `"é\n"` encodes to `b"&AOk-"`, so the newline disappears.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from twisted.mail import imap4

@settings(max_examples=1000)
@given(st.text())
def test_utf7_roundtrip(s):
    assert s.encode("imap4-utf-7").decode("imap4-utf-7") == s

@settings(max_examples=1000)
@given(st.text())
def test_utf7_ascii_output(s):
    e = s.encode("imap4-utf-7")
    assert all(0x20 <= b < 0x7f for b in e)
```

**Failing input**: `s='\r'` (round-trip); `s='\x1f\n\x1f'` (output contains a raw `\n`)

## Reproducing the Bug

```python
import twisted.mail.imap4

assert "\r".encode("imap4-utf-7") == b"&-"
assert b"&-".decode("imap4-utf-7") == "&"
assert "\nab".encode("imap4-utf-7").decode("imap4-utf-7") == "&ab"
assert "é\n".encode("imap4-utf-7") == b"&AOk-"
assert "é\té".encode("imap4-utf-7") == b"&AOk\t+AOk-"
```

## Why This Is A Bug

RFC 3501 section 5.1.3 says that only the printable US-ASCII characters 0x20-0x7e stand for themselves. Every other character must be base64-encoded, in UTF-16, inside an `&...-` shift. `encoder` gets this right for its own check (`valid_chars`) and sends `\t`, `\r` and `\n` to `modified_base64`. But `modified_base64` hands them to Python's standard `utf-7` codec, which writes tab, CR and LF directly instead of base64-encoding them. `modified_base64` then strips the first and last bytes of that output, assuming they are `+` and `-`. The result is one of three things:

- the character is dropped, e.g. `"\r"` becomes `b"&-"`, the escape for a literal `&`
- the last byte gets truncated
- the base64 section contains a raw control byte

Either way, the name that goes on the wire (`create`, `rename`, `list`, the server's LIST/STATUS replies, and so on) is silently corrupted. For example, a mailbox name containing `\n` becomes a different name containing `&`.

## Fix

```diff
--- a/src/twisted/mail/imap4.py
+++ b/src/twisted/mail/imap4.py
 def modified_base64(s):
-    s_utf7 = s.encode("utf-7")
-    return s_utf7[1:-1].replace(b"/", b",")
+    return binascii.b2a_base64(s.encode("utf-16-be"), newline=False).rstrip(
+        b"="
+    ).replace(b"/", b",")
 
 
 def modified_unbase64(s):
-    s_utf7 = b"+" + s.replace(b",", b"/") + b"-"
-    return s_utf7.decode("utf-7")
+    b64 = s.replace(b",", b"/")
+    b64 += b"=" * (-len(b64) % 4)
+    return binascii.a2b_base64(b64).decode("utf-16-be")
```

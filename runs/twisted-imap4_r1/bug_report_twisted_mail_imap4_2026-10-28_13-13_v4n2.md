# Bug Report: twisted.mail.imap4 imap4-utf-7 codec corrupts TAB, CR and LF

**Target**: `twisted.mail.imap4.encoder` / `modified_base64` (codec `"imap4-utf-7"`)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

The `imap4-utf-7` codec does not encode `\t`, `\n` and `\r` correctly. Depending on what surrounds them, these characters become the escape for `&`, get silently dropped, or produce bytes that fail to decode.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from twisted.mail import imap4

@settings(max_examples=1000)
@given(st.text())
def test_utf7_roundtrip(s):
    enc = s.encode("imap4-utf-7")
    assert enc.decode("imap4-utf-7") == s
```

**Failing input**: `s='\n'` (also `s='\n\x1f'`, which fails with an exception)

## Reproducing the Bug

```python
import twisted.mail.imap4

assert "a\tb".encode("imap4-utf-7") == b"a&-b"
assert "a\tb".encode("imap4-utf-7") == "a&b".encode("imap4-utf-7")
assert "é\t".encode("imap4-utf-7").decode("imap4-utf-7") == "é"
"\n\x1f".encode("imap4-utf-7").decode("imap4-utf-7")  # UnicodeDecodeError
```

## Why This Is A Bug

RFC 3501 §5.1.3 says only printable US-ASCII characters other than `&` represent themselves. Every other character, control characters included, must be encoded in modified BASE64 (UTF-16 inside `&...-`). The encoder sends `\t`, `\r` and `\n` to `modified_base64`. That function relies on Python's standard `utf-7` codec and slices off the leading `+` and trailing `-`. However, standard UTF-7 writes TAB, CR and LF directly, so the slice gives wrong output:

- If the run is only these characters, the slice is empty and the output is `&-`, which is the encoding of `&`. Different mailbox names (for example `"a\tb"` and `"a&b"`) then encode to the same bytes.
- If they follow non-ASCII characters, they fall outside the slice and are silently dropped.
- If they come first in a mixed run, the output looks like `&+AB8-`, which cannot be decoded.

The codec is used for mailbox names on both sides: `_prepareMailboxName` on the client and `_parseMbox` on the server. The result is silent name corruption or crashes. This also breaks the expected `decode(encode(s)) == s` property of a registered codec.

## Fix

Base64-encode the UTF-16BE bytes directly instead of using Python's UTF-7 codec, which applies different direct-character rules.

```diff
--- a/src/twisted/mail/imap4.py
+++ b/src/twisted/mail/imap4.py
@@ -16,6 +16,7 @@
 """
 from __future__ import annotations
 
+import base64
 import binascii
 import codecs
 import copy
@@ -6097,8 +6098,8 @@
 
 
 def modified_base64(s):
-    s_utf7 = s.encode("utf-7")
-    return s_utf7[1:-1].replace(b"/", b",")
+    s_utf16 = s.encode("utf-16-be")
+    return base64.b64encode(s_utf16).rstrip(b"=").replace(b"/", b",")
 
 
 def modified_unbase64(s):
```

With this patch the round-trip property passes over 1000 examples, and `src/twisted/mail/test/test_imap.py` has no new failures.

# Bug Report: twisted.mail.imap4 imap4-utf-7 codec corrupts TAB, CR and LF

**Target**: `twisted.mail.imap4.encoder` / `modified_base64` (codec `"imap4-utf-7"`)
**Severity**: Low
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`modified_base64` uses Python's `utf-7` codec and removes the first and last bytes, assuming the output is always `+<base64>-`. Standard UTF-7 encodes `\t`, `\n` and `\r` directly and not as base64, so this assumption fails. For example, `"\n"` encodes to `b"&-"`, which decodes back to `"&"`, and `"\n\u00e9"` encodes to `b"&+AOk-"`. The data is silently corrupted, and the encoded output is not valid modified UTF-7.

## Property-Based Test

```python
@given(st.text())
def test_utf7_roundtrip(s):
    """CLAIM-4: imap4-utf-7 round trip, 7-bit printable output."""
    b = s.encode("imap4-utf-7")
    assert all(0x20 <= c < 0x7F for c in b)
    assert b.decode("imap4-utf-7") == s
```

**Failing input**: `s='\n'`

## Reproducing the Bug

```python
import twisted.mail.imap4

for s in ["\n", "a\tb", "\n\u00e9"]:
    b = s.encode("imap4-utf-7")
    print(repr(s), b, repr(b.decode("imap4-utf-7")))
# '\n' b'&-' '&'
```

## Why This Is A Bug

An encode/decode codec pair must round-trip. RFC 3501 §5.1.3 requires characters outside 0x20-0x7e to be encoded as `&<modified-base64 of UTF-16BE>-`. Mailbox names that contain these control characters are renamed silently, both in client commands (`_prepareMailboxName`) and in server LIST responses.

## Fix

```diff
--- a/src/twisted/mail/imap4.py
+++ b/src/twisted/mail/imap4.py
@@ def modified_base64(s):
 def modified_base64(s):
-    s_utf7 = s.encode("utf-7")
-    return s_utf7[1:-1].replace(b"/", b",")
+    return (
+        binascii.b2a_base64(s.encode("utf-16-be"), newline=False)
+        .rstrip(b"=")
+        .replace(b"/", b",")
+    )
```

# Bug Report: twisted.mail.imap4 "imap4-utf-7" Codec Silently Turns TAB/CR/LF Into "&" or Drops Them

**Target**: `twisted.mail.imap4.encoder` / `modified_base64` (the `imap4-utf-7` codec)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`modified_base64` builds its output from Python's standard `utf-7` codec by slicing off the leading `+` and trailing `-`. Standard UTF-7 writes `\t`, `\n` and `\r` directly instead of base64-encoding them, so for those characters the slice is wrong:

- On its own, the shift sequence comes out empty (`&-`), which decodes back to `&`.
- Next to other non-ASCII characters, the characters are dropped or the output can't be decoded.

The data is corrupted without any error.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from twisted.mail import imap4  # registers the codec

@settings(max_examples=1000)
@given(st.text())
def test_utf7_roundtrip(s):
    assert s.encode("imap4-utf-7").decode("imap4-utf-7") == s
```

**Failing input**: `s='\n'` (also `'\n\x08'`, which raises `UnicodeDecodeError` on decode)

## Reproducing the Bug

```python
from twisted.mail import imap4

assert "a\tb".encode("imap4-utf-7") == b"a&-b"
assert b"a&-b".decode("imap4-utf-7") == "a&b"
assert "\u00e9\t".encode("imap4-utf-7").decode("imap4-utf-7") == "\u00e9"
"\n\x08".encode("imap4-utf-7").decode("imap4-utf-7")  # UnicodeDecodeError
```

## Why This Is A Bug

Under RFC 3501 §5.1.3, every character outside printable US-ASCII (0x20–0x7e) must be written in modified BASE64 of UTF-16. The encoder's own `valid_chars` set follows that rule, so control characters are meant to go through `modified_base64`. That function then mis-encodes TAB/CR/LF:

- A mailbox name containing those characters is sent to the server (via `_prepareMailboxName`) as a different name. For example, `a<TAB>b` is sent as `a&b`.
- Some inputs produce output that can't be decoded at all.

## Fix

```diff
--- a/src/twisted/mail/imap4.py
+++ b/src/twisted/mail/imap4.py
@@
 def modified_base64(s):
-    s_utf7 = s.encode("utf-7")
-    return s_utf7[1:-1].replace(b"/", b",")
+    return base64.b64encode(s.encode("utf-16-be")).rstrip(b"=").replace(b"/", b",")
```

(This needs `import base64`.) With this patch, the round-trip property passes and so does the existing `twisted.mail.test.test_imap` suite.

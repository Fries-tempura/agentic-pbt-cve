# Bug Report: twisted.mail.imap4 "imap4-utf-7" codec turns TAB/CR/LF into "&"

**Target**: `twisted.mail.imap4.encoder` (codec `imap4-utf-7`)
**Severity**: Low
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

Characters outside 0x20–0x7E are supposed to be base64-encoded inside `&...-`. For `\t`, `\n` and `\r`, `modified_base64` returns an empty string because Python's standard `utf-7` codec writes these characters directly instead of base64-encoding them. The encoder then outputs `&-`, which decodes to `&`, so the original character is silently replaced.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
import twisted.mail.imap4

@settings(max_examples=2000)
@given(st.text())
def test_utf7_roundtrip(s):
    enc = s.encode("imap4-utf-7")
    assert enc.decode("imap4-utf-7") == s
```

**Failing input**: `s='\n'`

## Reproducing the Bug

```python
import twisted.mail.imap4
print("Inbox\tx".encode("imap4-utf-7"))                       # b'Inbox&-x'
print("Inbox\tx".encode("imap4-utf-7").decode("imap4-utf-7"))  # 'Inbox&x'
```

## Why This Is A Bug

RFC 3501 §5.1.3 modified UTF-7 must round-trip, and other control characters do (`'\x01'` → `&AAE-`). Only TAB, CR and LF are lost, and they become a literal `&`.

## Fix

```diff
 def modified_base64(s):
-    s_utf7 = s.encode("utf-7")
-    return s_utf7[1:-1].replace(b"/", b",")
+    return (
+        binascii.b2a_base64(s.encode("utf-16-be"), newline=False)
+        .rstrip(b"=")
+        .replace(b"/", b",")
+    )
```

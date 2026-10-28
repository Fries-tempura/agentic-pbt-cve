# Bug Report: twisted.mail.imap4 imap4-utf-7 codec silently corrupts control characters

**Target**: `twisted.mail.imap4.encoder` (the `imap4-utf-7` codec)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`encoder` relies on Python's `utf-7` codec for the base64 part, but standard UTF-7 passes `\t`, `\n` and `\r` through as-is. So `modified_base64("\n")` returns `b""`, and the encoder outputs `&-`, which is the encoding of `&`. A mailbox name containing TAB, CR or LF is silently turned into `&`. When such a character comes right before a non-ASCII character, the output can't be decoded at all.

## Property-Based Test

```python
@settings(max_examples=1000)
@given(st.text(st.characters(exclude_categories=("Cs",))))
def test_utf7_roundtrip(s):
    assert s.encode("imap4-utf-7").decode("imap4-utf-7") == s
```

**Failing input**: `s='\n'`

## Reproducing the Bug

```python
import twisted.mail.imap4

assert "a\tb".encode("imap4-utf-7") == b"a&-b"
assert b"a&-b".decode("imap4-utf-7") == "a&b"
"\t\u00e9".encode("imap4-utf-7").decode("imap4-utf-7")  # UnicodeDecodeError
```

## Why This Is A Bug

RFC 3501 §5.1.3 says that every octet outside 0x20-0x7e must be encoded in modified BASE64. `&-` is reserved for a literal `&`. The codec breaks the round-trip that `_parseMbox` and `_prepareMailboxName` depend on: a mailbox name like `"a\tb"` comes back as `"a&b"`, and the server sees a different mailbox.

## Fix

```diff
 def modified_base64(s):
-    s_utf7 = s.encode("utf-7")
-    return s_utf7[1:-1].replace(b"/", b",")
+    s_utf16 = s.encode("utf-16-be")
+    return base64.b64encode(s_utf16).rstrip(b"=").replace(b"/", b",")
```
(`base64` needs to be imported. The decoder can be made symmetric in the same way.)

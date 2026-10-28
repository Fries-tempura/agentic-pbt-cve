# Bug Report: twisted.mail.imap4 imap4-utf-7 codec does not round-trip control characters

**Target**: `twisted.mail.imap4.encoder` / `twisted.mail.imap4.decoder` (codec `imap4-utf-7`)
**Severity**: Low
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`modified_base64` relies on Python's `utf-7` codec to produce a base64 shift sequence. But Python's UTF-7 writes `\t`, `\n` and `\r` directly instead of base64-encoding them. As a result:

- `"\n"` encodes to `b"&-"`, which is the encoding of `"&"`.
- Mixed strings such as `"\n\x1f"` encode to bytes that the decoder rejects with `UnicodeDecodeError`.

## Property-Based Test

```python
@settings(max_examples=1000)
@given(st.text().filter(lambda s: not any(0xD800 <= ord(c) <= 0xDFFF for c in s)))
def test_utf7_round_trip(s):
    """CLAIM-3: imap4-utf-7 round trip."""
    assert s.encode("imap4-utf-7").decode("imap4-utf-7") == s
```

**Failing input**: `s='\n'` (wrong result); `s='\n\x1f'` (UnicodeDecodeError)

## Reproducing the Bug

```python
import twisted.mail.imap4

assert "\n".encode("imap4-utf-7") == "&".encode("imap4-utf-7") == b"&-"
print(repr(b"&-".decode("imap4-utf-7")))
"\n\x1f".encode("imap4-utf-7").decode("imap4-utf-7")
```

The last line raises `UnicodeDecodeError: 'utf7' codec can't decode ... partial character in shift sequence`.

## Why This Is A Bug

`encoder` and `decoder` are registered together as one codec for "the IMAP4 specific variation of UTF-7". RFC 3501 §5.1.3 requires every character outside 0x20–0x7E to be base64-encoded, so the encoding must be reversible. Instead, two different mailbox names map to the same bytes, and some names that the server can encode cannot be decoded again.

## Fix

Encode to UTF-16-BE and base64 directly instead of going through Python's `utf-7` codec:

```diff
 def modified_base64(s):
-    s_utf7 = s.encode("utf-7")
-    return s_utf7[1:-1].replace(b"/", b",")
+    return base64.b64encode(s.encode("utf-16-be")).rstrip(b"=").replace(b"/", b",")
```

`modified_unbase64` should be changed the same way: pad the input and decode it as base64 followed by UTF-16-BE.

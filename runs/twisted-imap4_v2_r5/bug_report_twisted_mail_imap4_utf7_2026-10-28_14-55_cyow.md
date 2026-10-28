# Bug Report: twisted.mail.imap4 "imap4-utf-7" codec silently loses TAB, LF and CR

**Target**: `twisted.mail.imap4.encoder` (codec `imap4-utf-7`)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

Encoding a string that contains `\t`, `\n` or `\r` gives output that does not decode back to the input. A control character on its own becomes `&-`, which decodes to `&`. Next to another non-ASCII character, the control character is dropped or appears raw in the output.

## Property-Based Test

```python
@given(st.text())
@settings(max_examples=1000)
def test_utf7_roundtrip(s):
    """CLAIM-1: decode(encode(s)) == s."""
    assert s.encode("imap4-utf-7").decode("imap4-utf-7") == s


@given(st.text())
@settings(max_examples=1000)
def test_utf7_printable(s):
    """CLAIM-2: encoded bytes are printable ASCII."""
    assert all(0x20 <= b <= 0x7E for b in s.encode("imap4-utf-7"))
```

**Failing input**: `s='\n'` (round trip), `s='\x1f\n\x1f'` (non-printable output)

## Reproducing the Bug

```python
import twisted.mail.imap4

for s in ["\n", "\t", "\r", "a\nb", "\x1f\n"]:
    e = s.encode("imap4-utf-7")
    print(repr(s), e, repr(e.decode("imap4-utf-7")))
```

Output:
```
'\n' b'&-' '&'
'\t' b'&-' '&'
'\r' b'&-' '&'
'a\nb' b'a&-b' 'a&b'
'\x1f\n' b'&AB8-' '\x1f'
```

## Why This Is A Bug

The encoder sends every character outside 0x20–0x7E to `modified_base64`, which calls Python's standard `utf-7` codec and removes the first and last bytes, assuming they are `+` and `-`. Standard UTF-7 writes TAB, LF and CR directly rather than base64-encoding them, so that assumption fails. `"\n".encode("utf-7") == b"\n"`, and slicing `[1:-1]` leaves `b""`. As a result, the encoded output means something different from the input (`\n` becomes `&`). It can also contain raw control bytes, which RFC 3501 §5.1.3 does not allow in modified UTF-7. Mailbox names go through this codec on both the client and the server, so they are silently corrupted.

## Fix

Base64-encode the run as UTF-16BE directly, the way RFC 3501 §5.1.3 specifies, instead of relying on the standard UTF-7 codec:

```diff
 def modified_base64(s):
-    s_utf7 = s.encode("utf-7")
-    return s_utf7[1:-1].replace(b"/", b",")
+    return base64.b64encode(s.encode("utf-16-be")).rstrip(b"=").replace(b"/", b",")
```

(`import base64` is needed. `modified_unbase64` already decodes through `utf-7`, which accepts this form.)

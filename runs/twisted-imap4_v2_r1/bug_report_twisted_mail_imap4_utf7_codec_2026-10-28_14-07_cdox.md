# Bug Report: twisted.mail.imap4 "imap4-utf-7" codec silently loses TAB/LF/CR and can emit raw control bytes

**Target**: `twisted.mail.imap4.encoder` (codec `imap4-utf-7`)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

`encoder` base64-encodes each run of non-printable characters with `modified_base64`. That function calls Python's `utf-7` codec and then strips the first and last byte, assuming the result is always `+…-`. Python's UTF-7 writes `\t`, `\n` and `\r` directly instead of base64-encoding them, so the assumption breaks:

- `"\n"` encodes to `b"&-"`, which decodes back as `"&"`.
- `"é\n"` encodes to `b"&AOk-"`, so the newline is silently dropped.
- `"\x1f\n\x1f"` encodes to `b"&AB8\n+AB8-"`, which puts a raw LF and a stray `+` into the output.

## Property-Based Test

```python
@given(st.text())
def test_utf7_roundtrip(s):
    """CLAIM-3: imap4-utf-7 round trip, printable ASCII output."""
    assume(not any(0xD800 <= ord(c) <= 0xDFFF for c in s))
    e = s.encode("imap4-utf-7")
    assert all(0x20 <= b <= 0x7E for b in e)
    assert e.decode("imap4-utf-7") == s
```

**Failing input**: `s='\n'`

## Reproducing the Bug

```python
import twisted.mail.imap4

assert "\n".encode("imap4-utf-7").decode("imap4-utf-7") == "\n"
```

```python
import twisted.mail.imap4
print("\n".encode("imap4-utf-7"), "é\n".encode("imap4-utf-7"), "\x1f\n\x1f".encode("imap4-utf-7"))
```

## Why This Is A Bug

An encode/decode codec pair must round-trip. RFC 3501 §5.1.3 also requires every character outside 0x20–0x7e to be represented in modified BASE64, so mailbox-name output must never contain raw control bytes. This encoder:

- changes a mailbox name's contents without raising an error, for example turning `"\n"` into `"&"`;
- can put a bare LF into a protocol line, where `IMAP4Client.list`, `_prepareMailboxName` and others embed it.

## Fix

```diff
 def modified_base64(s):
-    s_utf7 = s.encode("utf-7")
-    return s_utf7[1:-1].replace(b"/", b",")
+    return base64.b64encode(s.encode("utf-16-be")).rstrip(b"=").replace(b"/", b",")
```

(Also add `import base64`. The fix makes the encoder base64-encode every non-printable run itself, as RFC 3501 specifies, instead of relying on Python's UTF-7 choice of which characters to write directly.)

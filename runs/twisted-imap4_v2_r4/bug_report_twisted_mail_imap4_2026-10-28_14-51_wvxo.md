# Bug Report: twisted.mail.imap4 imap4-utf-7 codec silently corrupts TAB, LF and CR

**Target**: `twisted.mail.imap4.encoder` / `modified_base64` (the `imap4-utf-7` codec)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

Encoding a string with `imap4-utf-7` turns `\t`, `\n` and `\r` into `&-`, which is the encoding of `&`. The decoded result is a different string, and no error is raised. These characters can also take neighbouring non-ASCII characters' base64 run with them.

## Property-Based Test

```python
@settings(max_examples=1000)
@given(st.text())
def test_utf7_round_trip(s):
    """CLAIM-1: imap4-utf-7 decode(encode(s)) == s."""
    assert s.encode("imap4-utf-7").decode("imap4-utf-7") == s
```

**Failing input**: `s='\n'`

## Reproducing the Bug

```python
import twisted.mail.imap4

for s in ["\n", "a\tb", "\x80\n"]:
    enc = s.encode("imap4-utf-7")
    print(repr(s), enc, repr(enc.decode("imap4-utf-7")))
```

Output:

```
'\n' b'&-' '&'
'a\tb' b'a&-b' 'a&b'
'\x80\n' b'&AIA-' '\x80'
```

## Why This Is A Bug

`encoder` says it encodes "the given unicode string using the IMAP4 specific variation of UTF-7", and it is registered as a codec together with `decoder`. RFC 3501 §5.1.3 requires every character outside printable US-ASCII to be base64-encoded, so modified UTF-7 can represent these characters. `modified_base64` builds its output by calling Python's standard UTF-7 encoder and stripping the first and last bytes. Standard UTF-7 writes whitespace directly, without base64. So the encoder ends up with an empty or truncated base64 run:

- `"\n"` becomes `&-`, which decodes to `&`.
- In `"\x80\n"`, the `\n` is dropped.

`_prepareMailboxName` uses this codec on mailbox names. So `client.create("a\tb")` asks the server to create the mailbox `a&b` instead, with no error.

## Fix

```diff
--- a/src/twisted/mail/imap4.py
+++ b/src/twisted/mail/imap4.py
@@
-from base64 import decodebytes, encodebytes
+from base64 import b64encode, decodebytes, encodebytes
@@
 def modified_base64(s):
-    s_utf7 = s.encode("utf-7")
-    return s_utf7[1:-1].replace(b"/", b",")
+    return b64encode(s.encode("utf-16-be")).rstrip(b"=").replace(b"/", b",")
```

With this patch, the round-trip test passes on 2,000 examples.

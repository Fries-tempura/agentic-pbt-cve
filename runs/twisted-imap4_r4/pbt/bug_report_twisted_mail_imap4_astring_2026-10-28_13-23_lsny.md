# Bug Report: twisted.mail.imap4.IMAP4Server.arg_astring does not handle quoted-string escapes

**Target**: `twisted.mail.imap4.IMAP4Server.arg_astring`
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-28

## Summary

The server parses a quoted string by splitting at the next `"` and ignoring RFC 3501 backslash escapes. A `\"` inside a quoted string cuts the argument short and leaves the rest in the following arguments. A `\\` comes through as two backslashes. Twisted's own client escapes strings this way (`_quote`, used by `IMAP4Client.login`), so with the Twisted client and server together, any username or password that contains `"` or `\` arrives changed.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st
from twisted.mail.imap4 import IMAP4Server, _quote
from twisted.internet.testing import StringTransport

printable = st.binary().map(lambda b: bytes(c for c in b if 0x20 <= c < 0x7f))

@settings(max_examples=1000)
@given(printable, printable)
def test_client_quote_server_astring_roundtrip(user, password):
    s = IMAP4Server(); s.makeConnection(StringTransport())
    line = _quote(user) + b" " + _quote(password)
    u, rest = s.arg_astring(line)
    p, rest2 = s.arg_astring(rest)
    assert (u, p) == (user, password)
```

**Failing input**: `user=b'', password=b'\\'`

## Reproducing the Bug

```python
from twisted.mail.imap4 import IMAP4Server
from twisted.internet.testing import StringTransport

s = IMAP4Server()
s.makeConnection(StringTransport())
print(s.arg_astring(rb'"pa\"ss" next'))   # (b'pa\\', b's" next')   expected (b'pa"ss', b'next')
print(s.arg_astring(rb'"pa\\ss" next'))   # (b'pa\\\\ss', b'next')  expected (b'pa\\ss', b'next')
```

## Why This Is A Bug

RFC 3501 §9 defines `quoted = DQUOTE *QUOTED-CHAR DQUOTE` with `QUOTED-CHAR = ... / "\" quoted-specials`. `IMAP4Client.login` and `_prepareMailboxName` send strings in this escaped form. Because the server doesn't decode them, a LOGIN with a password containing `"` or `\` fails, even between a Twisted client and a Twisted server. Mailbox names with these characters are also mangled. For `\"`, the server reads the wrong argument boundaries too: the text after the escaped quote is treated as further arguments.

## Fix

```diff
         if line[0:1] == b'"':
-            try:
-                spam, arg, rest = line.split(b'"', 2)
-                rest = rest[1:]  # Strip space
-            except ValueError:
-                raise IllegalClientResponse("Unmatched quotes")
+            i = 1
+            buf = bytearray()
+            while True:
+                if i >= len(line):
+                    raise IllegalClientResponse("Unmatched quotes")
+                c = line[i : i + 1]
+                if c == b"\\" and line[i + 1 : i + 2] in (b"\\", b'"'):
+                    buf += line[i + 1 : i + 2]
+                    i += 2
+                elif c == b'"':
+                    break
+                else:
+                    buf += c
+                    i += 1
+            arg = bytes(buf)
+            rest = line[i + 2 :]  # Skip closing quote and space
```

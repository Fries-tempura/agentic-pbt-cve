# Bug Report: ldap.dn.escape_dn_chars Escapes NUL Incorrectly

**Target**: `ldap.dn.escape_dn_chars` (and `ldap.dn.dn2str`, which calls it)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`escape_dn_chars` turns a NUL character into a backslash followed by a raw NUL byte (`'\\\x00'`). RFC 4514 section 2.4 says NUL must be escaped as the hex pair `\00`. The result is not a valid DN. `str2dn` cannot parse it, so the documented inverse relationship between `dn2str` and `str2dn` is broken. Applications that use `escape_dn_chars` to sanitize untrusted input when building DNs can therefore produce malformed DNs.

## Property-Based Test

```python
import ldap.dn as D
from hypothesis import given, settings, strategies as st

avalue = st.text(st.characters(blacklist_categories=('Cs',), blacklist_characters='\t\n\r\x0b\x0c'), min_size=1)

@settings(max_examples=3000)
@given(avalue)
def test_escape_roundtrip(v):
    s = 'cn=' + D.escape_dn_chars(v)
    assert [[(t, x) for t, x, _ in r] for r in D.str2dn(s)] == [[('cn', v)]]
```

**Failing input**: `v='\x00'`

## Reproducing the Bug

```python
import ldap.dn as D

s = D.dn2str([[('cn', 'a\x00b', 1)]])
print(repr(s))
print(D.is_dn(s))
D.str2dn(s)
print(D.str2dn(r'cn=a\00b'))
```

Output:
```
'cn=a\\\x00b'
False
ldap.DECODING_ERROR
[[('cn', 'a\x00b', 4)]]
```

## Why This Is A Bug

The docstring says `escape_dn_chars` escapes all DN special characters "with a back-slash (see RFC 4514, section 2.4)". RFC 4514 section 2.4 requires NUL (U+0000) to be escaped as `\00`. A backslash followed by a raw NUL is not a valid escape sequence. The `dn2str` docstring says it is the inverse of `str2dn` and returns RFC 4514-compliant output. However, `str2dn(dn2str(dn))` raises `DECODING_ERROR` for any attribute value containing NUL, while the correctly escaped form `cn=a\00b` parses without error. If an application uses this function to sanitize untrusted values in DNs, attacker-supplied NUL bytes produce malformed DNs.

## Fix

```diff
--- a/Lib/ldap/dn.py
+++ b/Lib/ldap/dn.py
@@ def escape_dn_chars(s):
     s = s.replace(';' ,'\;')
     s = s.replace('=' ,'\\=')
-    s = s.replace('\000' ,'\\\000')
+    s = s.replace('\000' ,'\\00')
     if s[-1]==' ':
```

# Bug Report: ldap.dn.escape_dn_chars Escapes NUL as an Invalid `\<NUL>` Sequence

**Target**: `ldap.dn.escape_dn_chars` (and `ldap.dn.dn2str`, `explode_dn`, `explode_rdn`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`escape_dn_chars` turns a NUL character into a backslash followed by a raw NUL byte (`'\\\x00'`). RFC 4514 does not allow that sequence; NUL must be written as the hex pair `\00`. As a result, `dn2str()` can return a string that its own documented inverse, `str2dn()`, cannot parse. Values passed through the escaping function also still contain a raw NUL byte.

## Property-Based Test

```python
import ldap.dn as D
from hypothesis import given, settings, strategies as st

atype = st.from_regex(r'[a-zA-Z][a-zA-Z0-9-]{0,8}', fullmatch=True)

@settings(max_examples=2000)
@given(atype, st.text(min_size=1))
def test_escape_value_roundtrip(t, v):
    s = t + '=' + D.escape_dn_chars(v)
    assert D.str2dn(s)[0][0][1] == v
```

**Failing input**: `t='A', v='\x00'`

## Reproducing the Bug

```python
import ldap.dn

s = ldap.dn.dn2str([[('cn', 'a\x00b', 1)]])
print(repr(s))
print(ldap.dn.is_dn(s))
ldap.dn.str2dn(s)
```

Output: `'cn=a\\\x00b'`, then `False`, then `ldap.DECODING_ERROR`.

## Why This Is A Bug

- `escape_dn_chars` says it escapes special characters "see RFC 4514, section 2.4". Section 2.4 says NUL (U+0000) must be escaped as `\00`. The backslash-plus-raw-NUL form is not valid there.
- The `dn2str` docstring says it is "the inverse to str2dn()" and returns RFC 4514-compliant output. For any value containing NUL, its output is rejected by `str2dn`, `is_dn`, `normalize`, `explode_dn` and `explode_rdn`.
- The raw NUL byte stays in the escaped value. If the value goes to the C library or a server, the string is cut off at the NUL. Code that builds DNs or filters from untrusted input with this function could get a different DN than intended, so this is a security issue.

## Fix

```diff
--- a/Lib/ldap/dn.py
+++ b/Lib/ldap/dn.py
@@ def escape_dn_chars(s):
     s = s.replace(';' ,'\\;')
     s = s.replace('=' ,'\\=')
-    s = s.replace('\000' ,'\\\000')
+    s = s.replace('\000' ,'\\00')
     if s[-1]==' ':
```

With this change, `ldap.dn.str2dn('cn=a\\00b')` returns `[[('cn', 'a\x00b', 4)]]`, so the round trip works.

## Related observation (lower severity)

`escape_dn_chars` only escapes a leading or trailing space (`' '`). OpenLDAP's parser also strips leading and trailing `\t`, `\n` and `\r`. So the round trip quietly changes these values: `dn2str([[('cn','\n',1)]])` becomes `'cn=\n'`, and parsing that gives the value `''`. Likewise, `'\tb'` comes back as `'b'`. Escaping these characters as hex pairs (`\09`, `\0a`, `\0d`) at the edges of a value would preserve them.

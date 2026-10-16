# Bug Report: ldap.dn.escape_dn_chars escapes NUL as backslash+NUL instead of `\00`

**Target**: `ldap.dn.escape_dn_chars` (and `ldap.dn.dn2str`)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`escape_dn_chars` turns a NUL character into `\` followed by a raw NUL. RFC 4514 §2.4 says NUL must be escaped as `\00`. The output isn't a valid DN: `str2dn` rejects it with `DECODING_ERROR`, so `str2dn(dn2str(dn))` doesn't round-trip, even though `str2dn` is documented as the inverse of `dn2str`.

## Property-Based Test

```python
import ldap.dn as D
from hypothesis import given, settings, strategies as st

attr = st.from_regex(r'\A[a-zA-Z][a-zA-Z0-9-]{0,8}\Z')
val = st.text(min_size=1)
dnst = st.lists(st.lists(st.tuples(attr, val, st.just(1)), min_size=1, max_size=3), min_size=1, max_size=4)

@settings(max_examples=2000)
@given(dnst)
def test_roundtrip(dn):
    s = D.dn2str(dn)
    back = D.str2dn(s)
    assert [[(a, v) for a, v, _ in r] for r in back] == [[(a, v) for a, v, _ in r] for r in dn]
```

**Failing input**: `dn=[[('A', '\x00', 1)]]`

## Reproducing the Bug

```python
import ldap.dn

s = ldap.dn.dn2str([[('cn', 'a\x00b', 1)]])
print(repr(s))                     # 'cn=a\\\x00b'
print(ldap.dn.is_dn(s))            # False
ldap.dn.str2dn(s)                  # ldap.DECODING_ERROR
print(ldap.dn.str2dn(r'cn=a\00b')) # [[('cn', 'a\x00b', 4)]]  <- correct escaping parses fine
```

## Why This Is A Bug

The docstring says the function escapes "with a back-slash (see RFC 4514, section 2.4)". RFC 4514 requires NUL to be written as the hex pair `\00`. Because NUL is mis-escaped, `dn2str` produces DNs that `str2dn`, `explode_dn`, `is_dn` and the LDAP server reject. Applications that use `escape_dn_chars` to sanitise untrusted input when building DNs or filters can then fail when an attacker supplies a NUL byte (a DoS / request-failure vector; compare CVE-2025-61912).

## Fix

```diff
-    s = s.replace('\000' ,'\\\000')
+    s = s.replace('\000' ,'\\00')
```

## Note (minor, related)

Values that start or end with whitespace other than a space (`'\n'`, `'\t'`) aren't escaped. OpenLDAP's `str2dn` strips that whitespace, so `str2dn(dn2str([[('cn','\n',1)]]))` returns `''`. RFC 4514 only requires escaping a leading or trailing SPACE, so this is a lesser interoperability issue. It could be fixed by hex-escaping leading and trailing whitespace.

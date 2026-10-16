# Bug Report: ldap.dn.escape_dn_chars Escapes NUL as Backslash + Raw NUL, Producing Unparseable DNs

**Target**: `ldap.dn.escape_dn_chars` (also affects `ldap.dn.dn2str`, `explode_dn`, `explode_rdn`, `normalize`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

`escape_dn_chars` turns `'\x00'` into `'\\\x00'`: a backslash followed by a raw NUL byte. RFC 4514 §2.4 says NUL must be written in hex as `\00`. A backslash followed by a raw NUL is not valid, so any DN built from a value that contains NUL can't be parsed. `str2dn` raises `ldap.DECODING_ERROR`. An application that builds DNs from untrusted input with this helper can be made to fail on every such request (denial of service).

## Property-Based Test

```python
import ldap, ldap.dn
from hypothesis import given, settings, strategies as st

@settings(max_examples=2000)
@given(st.text(min_size=1))
def test_escape_roundtrip(v):
    s = 'cn=' + ldap.dn.escape_dn_chars(v)
    parsed = ldap.dn.str2dn(s)
    assert len(parsed) == 1 and len(parsed[0]) == 1
    assert parsed[0][0][1] == v

@settings(max_examples=1000)
@given(st.lists(st.lists(st.tuples(st.from_regex(r'\A[a-zA-Z][a-zA-Z0-9-]{0,10}\Z'),
                                    st.text(min_size=1)), min_size=1, max_size=3),
                min_size=1, max_size=4))
def test_dn2str_str2dn(d):
    s = ldap.dn.dn2str([[(t, v, 1) for t, v in r] for r in d])
    back = ldap.dn.str2dn(s)
    assert [[(t, v) for t, v, _ in r] for r in back] == d
```

**Failing input**: `d=[[('A', '\x00')]]` (and `v='\x00'`)

## Reproducing the Bug

```python
import ldap.dn

print(repr(ldap.dn.escape_dn_chars('\x00')))
ldap.dn.str2dn('cn=' + ldap.dn.escape_dn_chars('a\x00b'))
ldap.dn.dn2str([[('cn', '\x00', 1)]])
ldap.dn.normalize(ldap.dn.dn2str([[('cn', '\x00', 1)]]))
```

Output: `'\\\x00'`, then `ldap.DECODING_ERROR` from `str2dn`/`normalize`. The correct escape is accepted: `ldap.dn.str2dn(r'cn=a\00b') == [[('cn', 'a\x00b', 4)]]`.

## Why This Is A Bug

The docstring says `escape_dn_chars` escapes DN special characters "see RFC 4514, section 2.4", and that section requires NUL to be hex-escaped as `\00`. `str2dn` is documented as the inverse of `dn2str`, but that inverse property breaks for every value containing NUL. Because this is the library's escaping helper for untrusted values, attacker-supplied NUL bytes reliably make DN construction and parsing fail.

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
       s = ''.join((s[:-1],'\\ '))
```

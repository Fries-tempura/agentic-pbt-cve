# Bug Report: ldap.dn.escape_dn_chars Emits Invalid Escape for NUL Characters

**Target**: `ldap.dn.escape_dn_chars` (also affects `ldap.dn.dn2str`, `explode_dn`, `explode_rdn`)
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`escape_dn_chars` escapes a NUL character (`\x00`) as a backslash followed by a literal NUL byte (`'\\\x00'`). RFC 4514 §2.4 says NUL must be escaped as the hex pair `\00`. The output is not a valid DN, so `str2dn` rejects it with `ldap.DECODING_ERROR`. This breaks the round trip `str2dn(dn2str(x)) == x` that the docstrings promise. It also means the output can't safely be put into DNs/filters handed to LDAP servers.

## Property-Based Test

```python
import ldap, ldap.dn
from hypothesis import given, settings, strategies as st

vals = st.text(st.characters(blacklist_categories=('Cs',)), min_size=1)
types = st.from_regex(r'\A[a-zA-Z][a-zA-Z0-9-]{0,10}\Z')

@settings(max_examples=2000)
@given(types, vals)
def test_escape_roundtrip(t, v):
    dn = t + '=' + ldap.dn.escape_dn_chars(v)
    parsed = ldap.dn.str2dn(dn)
    assert len(parsed) == 1 and len(parsed[0]) == 1
    assert parsed[0][0][1] == v

@settings(max_examples=1000)
@given(st.lists(st.lists(st.tuples(types, vals), min_size=1, max_size=3), min_size=1, max_size=4))
def test_dn2str_str2dn_roundtrip(dn):
    d = [[(a, v, 1) for a, v in rdn] for rdn in dn]
    back = ldap.dn.str2dn(ldap.dn.dn2str(d))
    assert [[(a, v) for a, v, _ in rdn] for rdn in back] == dn
```

**Failing input**: `t='A', v='\x00'` / `dn=[[('A', '\x00')]]`

## Reproducing the Bug

```python
import ldap.dn

print(repr(ldap.dn.escape_dn_chars('a\x00b')))   # 'a\\\x00b'  (backslash + raw NUL)
ldap.dn.str2dn(ldap.dn.dn2str([[('cn', 'a\x00b', 1)]]))  # raises ldap.DECODING_ERROR
print(ldap.dn.str2dn('cn=a\\00b'))               # correct escape parses fine: [[('cn', 'a\x00b', 4)]]
```

## Why This Is A Bug

The docstring says `escape_dn_chars` escapes DN special characters "see RFC 4514, section 2.4". That section says NUL must be escaped as `\00`. Backslash followed by a raw NUL is not a valid escape sequence. `dn2str` is documented as "the inverse to str2dn()" and RFC 4514 compliant, but for any value that contains NUL its output can't be parsed back. Applications that build DNs from untrusted input with `escape_dn_chars` get a malformed DN with an embedded raw NUL. C-level LDAP code may truncate a string like that at the NUL, which can change the DN (this corresponds to CVE-2025-61912).

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

## Secondary observation (Low)

Leading or trailing whitespace other than the space character (`\r`, `\t`) is not escaped, and `str2dn` silently strips it. For example, `escape_dn_chars('a\r')` → `'a\r'`, and `str2dn('cn=a\r')` → `[[('cn', 'a', 4)]]`. Escaping these as hex (`\0D`, `\09`) at the value's edges would keep the round trip intact.

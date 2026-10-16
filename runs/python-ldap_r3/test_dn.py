import ldap, ldap.dn
from hypothesis import given, settings, strategies as st, assume

atype = st.from_regex(r'\A[a-zA-Z][a-zA-Z0-9-]{0,10}\Z')
aval = st.text(min_size=1)
rdn = st.lists(st.tuples(atype, aval), min_size=1, max_size=3)
dn = st.lists(rdn, min_size=1, max_size=4)

@settings(max_examples=2000)
@given(aval)
def test_escape_roundtrip(v):
    s = 'cn=' + ldap.dn.escape_dn_chars(v)
    parsed = ldap.dn.str2dn(s)
    assert len(parsed) == 1 and len(parsed[0]) == 1
    assert parsed[0][0][1] == v

@settings(max_examples=1000)
@given(dn)
def test_dn2str_str2dn(d):
    dd = [[(t, v, 1) for t, v in r] for r in d]
    s = ldap.dn.dn2str(dd)
    back = ldap.dn.str2dn(s)
    assert [[(t, v) for t, v, _ in r] for r in back] == [[(t, v) for t, v in r] for r in d]

@settings(max_examples=1000)
@given(dn)
def test_explode_dn(d):
    s = ldap.dn.dn2str([[(t, v, 1) for t, v in r] for r in d])
    parts = ldap.dn.explode_dn(s)
    assert ','.join(parts) == s

@settings(max_examples=1000)
@given(rdn)
def test_explode_rdn_notypes(r):
    s = ldap.dn.dn2str([[(t, v, 1) for t, v in r]])
    assert ldap.dn.explode_rdn(s, notypes=True) == [v for t, v in r]

@settings(max_examples=1000)
@given(dn)
def test_normalize_idempotent(d):
    s = ldap.dn.dn2str([[(t, v, 1) for t, v in r] for r in d])
    n = ldap.dn.normalize(s)
    assert ldap.dn.normalize(n) == n

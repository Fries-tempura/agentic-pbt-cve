import ldap, ldap.dn as D
from hypothesis import given, settings, strategies as st, assume

atype = st.from_regex(r'[a-zA-Z][a-zA-Z0-9-]{0,8}', fullmatch=True)
aval = st.text(min_size=1)
ava = st.tuples(atype, aval, st.just(1))
rdn = st.lists(ava, min_size=1, max_size=3)
dnlist = st.lists(rdn, min_size=1, max_size=4)

@settings(max_examples=2000)
@given(dnlist)
def test_roundtrip(dn):
    s = D.dn2str(dn)
    back = D.str2dn(s)
    assert [[(a, v) for a, v, _ in r] for r in back] == [[(a, v) for a, v, _ in r] for r in dn], s

@settings(max_examples=2000)
@given(atype, aval)
def test_escape_value_roundtrip(t, v):
    s = t + '=' + D.escape_dn_chars(v)
    assert D.str2dn(s)[0][0][1] == v

@settings(max_examples=1000)
@given(dnlist)
def test_normalize_idempotent(dn):
    s = D.dn2str(dn)
    assert D.is_dn(s)
    n = D.normalize(s)
    assert D.normalize(n) == n

@settings(max_examples=1000)
@given(dnlist)
def test_explode_rdn_values(dn):
    s = D.dn2str([dn[0]])
    assert D.explode_rdn(s, notypes=True) == [v for _, v, _ in dn[0]]

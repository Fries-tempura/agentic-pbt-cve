import ldap.dn as D
from hypothesis import given, settings, strategies as st

atype = st.sampled_from(['cn','ou','o','dc','uid','l'])
avalue = st.text(min_size=1)
rdn = st.lists(st.tuples(atype, avalue), min_size=1, max_size=3)
dn = st.lists(rdn, min_size=1, max_size=4)

@settings(max_examples=2000)
@given(avalue)
def test_escape_roundtrip(v):
    s = 'cn=' + D.escape_dn_chars(v)
    assert D.str2dn(s) == [[('cn', v, 1)]], (s,)

@settings(max_examples=1000)
@given(dn)
def test_dn2str_str2dn_roundtrip(d):
    s = D.dn2str([[(t, v, 1) for t, v in r] for r in d])
    parsed = D.str2dn(s)
    assert [[(t, v) for t, v, _ in r] for r in parsed] == d

@settings(max_examples=1000)
@given(dn)
def test_explode_dn(d):
    s = D.dn2str([[(t, v, 1) for t, v in r] for r in d])
    assert ','.join(D.explode_dn(s)) == s

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
    s = ldap.dn.dn2str(d)
    back = ldap.dn.str2dn(s)
    assert [[(a, v) for a, v, _ in rdn] for rdn in back] == dn

@settings(max_examples=1000)
@given(st.lists(st.tuples(types, vals), min_size=1, max_size=4))
def test_explode_dn_len(rdns):
    s = ','.join(t + '=' + ldap.dn.escape_dn_chars(v) for t, v in rdns)
    assert len(ldap.dn.explode_dn(s)) == len(rdns)

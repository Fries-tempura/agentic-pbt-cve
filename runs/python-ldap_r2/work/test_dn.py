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

@settings(max_examples=2000)
@given(val)
def test_escape_roundtrip(v):
    s = 'cn=' + D.escape_dn_chars(v)
    assert D.str2dn(s)[0][0][1] == v

@settings(max_examples=2000)
@given(dnst)
def test_explode(dn):
    s = D.dn2str(dn)
    assert ','.join(D.explode_dn(s)) == s
    assert D.is_dn(s)

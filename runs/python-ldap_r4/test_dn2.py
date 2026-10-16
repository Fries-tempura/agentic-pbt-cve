import ldap.dn as D
from hypothesis import given, settings, strategies as st

avalue = st.text(st.characters(blacklist_categories=('Cs',), blacklist_characters='\t\n\r\x0b\x0c\x00'), min_size=1)

@settings(max_examples=3000)
@given(avalue)
def test_escape_roundtrip(v):
    s = 'cn=' + D.escape_dn_chars(v)
    assert [[(t, x) for t, x, _ in r] for r in D.str2dn(s)] == [[('cn', v)]]

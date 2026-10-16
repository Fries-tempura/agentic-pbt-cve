import ldap.dn as D
for s in [r'cn=\00', r'cn=a\00b']:
    print(repr(s), D.str2dn(s))
print(repr(D.escape_dn_chars('\x00')), D.is_dn(D.dn2str([[('cn','a\x00',1)]])))
try: D.explode_dn(D.dn2str([[('cn','a\x00',1)]]))
except Exception as e: print(repr(e))

import ldap.dn as D
for v in ['\n', '\x00', 'a\x00b', ' ', '#', 'a ', '\\', 'é']:
    s = D.dn2str([[('cn', v, 1)]])
    try: r = D.str2dn(s)
    except Exception as e: r = repr(e)
    print(repr(v), repr(s), r)

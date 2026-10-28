from twisted.mail import imap4
for s in ["\n", "\t", "a\tb", "\r\n", "\té"]:
    e = s.encode("imap4-utf-7")
    try: d = e.decode("imap4-utf-7")
    except Exception as ex: d = repr(ex)
    print(repr(s), e, repr(d))
print("---messageset")
m = imap4.MessageSet()
print(len(m))
try: print(list(m))
except Exception as ex: print(type(ex), ex)
try: print(1 in m)
except Exception as ex: print(type(ex), ex)
print("---quote")
for w in [b"C:\\", b"a\\b", b'say "hi"']:
    s = imap4.collapseNestedLists([w])
    try: print(s, imap4.parseNestedParens(s))
    except Exception as ex: print(s, type(ex), ex)
print("---wildcard")
acct = imap4.MemoryAccount("u")
for n in ["INBOX2", "foo", "foobar", "aXb", "Work (old)"]:
    acct.create(n)
for pat in ["INBOX", "foo", "a.b", "Work (old)"]:
    try: print(pat, [n for n, _ in acct.listMailboxes("", pat)])
    except Exception as ex: print(pat, type(ex), ex)

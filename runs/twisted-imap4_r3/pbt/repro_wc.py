from twisted.mail import imap4
acct = imap4.MemoryAccount("u")
for n in ["INBOX2", "foo", "foobar", "aXb", "Work (old)"]:
    acct.addMailbox(n, object())
for pat in ["INBOX", "FOO", "A.B", "WORK (OLD)"]:
    try: print(pat, [n for n, _ in acct.listMailboxes("", pat)])
    except Exception as ex: print(pat, type(ex), ex)

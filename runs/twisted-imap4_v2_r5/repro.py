import time
from twisted.mail import imap4
for s in ["\n", "\t", "\r", "a\nb", "\x1f\n"]:
    e = s.encode("imap4-utf-7")
    try: d = e.decode("imap4-utf-7")
    except Exception as ex: d = repr(ex)
    print(repr(s), e, repr(d))
acct = imap4.MemoryAccount("u")
for n in ["INBOX", "INBOXES", "AXB", "a" * 26 + "!"]:
    acct.addMailbox(n, object())
print([n for n,_ in acct.listMailboxes("", "INBOX")])
print([n for n,_ in acct.listMailboxes("", "a.b")])
try: acct.listMailboxes("", "[")
except Exception as ex: print(type(ex), ex)
for k in (20, 22, 24, 26):
    a = imap4.MemoryAccount("u"); a.addMailbox("a"*k+"!", object())
    t=time.perf_counter(); a.listMailboxes("", "(a+)+$"); print(k, round(time.perf_counter()-t,2))

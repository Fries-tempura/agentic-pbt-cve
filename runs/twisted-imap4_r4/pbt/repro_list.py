from twisted.mail.imap4 import splitQuoted, parseNestedParens, IMAP4Client
from twisted.internet.testing import StringTransport

for s in [rb'"a\\b"', rb'"foo\\"', rb'() "\\" INBOX']:
    for f in (splitQuoted, parseNestedParens):
        try: print(f.__name__, s, '->', f(s))
        except Exception as e: print(f.__name__, s, '->', repr(e))

c = IMAP4Client()
c.makeConnection(StringTransport())
c.lineReceived(b'* OK [IMAP4rev1] ready')
d = c.list(b"", b"*")
res = []
d.addBoth(res.append)
c.lineReceived(rb'* LIST (\HasNoChildren) "\\" INBOX')
c.lineReceived(b'0001 OK LIST done')
print(res)

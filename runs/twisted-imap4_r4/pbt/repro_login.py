from twisted.mail.imap4 import IMAP4Server
from twisted.internet.testing import StringTransport
s = IMAP4Server(); s.makeConnection(StringTransport())
for line in [rb'"pa\"ss" next', rb'"pa\\ss" next']:
    print(line, '->', s.arg_astring(line))

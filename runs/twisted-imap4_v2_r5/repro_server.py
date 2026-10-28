import time
from twisted.internet.testing import StringTransport
from twisted.mail import imap4

class Box:
    def getFlags(self): return []
    def getHierarchicalDelimiter(self): return "/"

acct = imap4.MemoryAccount("u")
acct.addMailbox("a" * 27 + "!", Box())
server = imap4.IMAP4Server()
server.makeConnection(StringTransport())
server.account, server.state = acct, "auth"
t = time.perf_counter()
server.dataReceived(b'A1 LIST "" "(a+)+$"\r\n')
print(round(time.perf_counter() - t, 2), "s", server.transport.value().splitlines()[-1])

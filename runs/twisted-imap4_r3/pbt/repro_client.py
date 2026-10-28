from twisted.mail import imap4
from twisted.internet.testing import StringTransport

def run(line):
    c = imap4.IMAP4Client()
    c.makeConnection(StringTransport())
    c.state = "AUTH"
    c.lineReceived(b"* OK ready")
    d = c.list("", "*")
    res = []
    d.addBoth(res.append)
    c.dataReceived(line + b"\r\n0001 OK done\r\n")
    return res

print(run(b'* LIST () "/" "a\\\\b"'))
print(run(b'* LIST () "/" "C:\\\\"'))

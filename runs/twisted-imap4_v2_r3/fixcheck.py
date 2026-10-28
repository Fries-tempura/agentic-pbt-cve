import binascii, time, re
from hypothesis import given, settings, strategies as st
from twisted.mail import imap4
import test_imap4 as T

def modified_base64(s):
    return binascii.b2a_base64(s.encode("utf-16-be"), newline=False).rstrip(b"=").replace(b"/", b",")
imap4.modified_base64 = modified_base64

def globMatch(wildcard, name, delim=None):
    # linear-space DP glob match: '*' any, '%' any except delim
    wildcard, name = wildcard.casefold(), name.casefold()
    states = {0}
    def close(st):
        out, todo = set(st), list(st)
        while todo:
            i = todo.pop()
            if i < len(wildcard) and wildcard[i] in "*%" and i + 1 not in out:
                out.add(i + 1); todo.append(i + 1)
        return out
    states = close(states)
    for ch in name:
        nxt = set()
        for i in states:
            if i == len(wildcard): continue
            w = wildcard[i]
            if w == "*" or (w == "%" and ch != delim): nxt.add(i)
            elif w == ch: nxt.add(i + 1)
        states = close(nxt)
        if not states: return False
    return len(wildcard) in states

def listMailboxes(self, ref, wildcard):
    ref = self._inferiorNames(imap4._parseMbox(ref.upper()))
    return [(i, self.mailboxes[i]) for i in ref if globMatch(wildcard, i, "/")]
imap4.MemoryAccountWithoutNamespaces.listMailboxes = listMailboxes

if __name__ == "__main__":
    for f in (T.test_list_matches_reference, T.test_list_no_crash, T.test_utf7_roundtrip, T.test_list_cost):
        f(); print(f.__name__, "ok")

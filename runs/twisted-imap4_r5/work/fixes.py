import base64, re, string
from twisted.mail import imap4
from twisted.python.compat import iterbytes

def modified_base64(s):
    return base64.b64encode(s.encode("utf-16-be")).rstrip(b"=").replace(b"/", b",")

def wildcardToRegexp(wildcard, delim=None):
    parts = []
    for c in wildcard:
        if c == "*" or (c == "%" and delim is None):
            parts.append("(?:.*?)")
        elif c == "%":
            parts.append("(?:(?:[^%s])*?)" % re.escape(delim))
        else:
            parts.append(re.escape(c))
    return re.compile("".join(parts), re.I)

def splitQuoted(s):
    s = s.strip()
    result = []
    word = []
    inQuote = inWord = escaped = False
    qu, esc, empty, nil = b'"', b"\\", b"", b"NIL"
    for i, c in enumerate(iterbytes(s)):
        if c == qu:
            if escaped:
                word.pop()
                word.append(qu)
            elif not inQuote:
                inQuote = True
            else:
                inQuote = False
                result.append(empty.join(word))
                word = []
        elif (
            not inWord
            and not inQuote
            and c not in (qu + (string.whitespace.encode("ascii")))
        ):
            inWord = True
            word.append(c)
        elif inWord and not inQuote and c in string.whitespace.encode("ascii"):
            w = empty.join(word)
            if w == nil:
                result.append(None)
            else:
                result.append(w)
            word = []
            inWord = False
        elif inWord or inQuote:
            word.append(c)
        escaped = c == esc and not escaped

    if inQuote:
        raise imap4.MismatchedQuoting(s)
    if inWord:
        w = empty.join(word)
        if w == nil:
            result.append(None)
        else:
            result.append(w)

    return result

imap4.modified_base64 = modified_base64
imap4.wildcardToRegexp = wildcardToRegexp
imap4.splitQuoted = splitQuoted

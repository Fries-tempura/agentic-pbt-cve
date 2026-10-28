import re
from twisted.mail import imap4

def wildcardToRegexp(wildcard, delim=None):
    if delim is None:
        percent = "(?:.*?)"
    else:
        percent = "(?:[^%s]*?)" % re.escape(delim)
    parts = []
    for tok in re.split(r"([*%]+)", wildcard):
        if not tok:
            continue
        if tok[0] in "*%":
            parts.append("(?:.*?)" if "*" in tok else percent)
        else:
            parts.append(re.escape(tok))
    return re.compile("".join(parts) + r"\Z", re.I | re.S)

imap4.wildcardToRegexp = wildcardToRegexp

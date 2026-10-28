# Claims for twisted.mail.imap4

## CLAIM-1
- evidence: twisted/mail/interfaces.py:982-986 (IAccount.listMailboxes, implemented by MemoryAccountWithoutNamespaces.listMailboxes via wildcardToRegexp, imap4.py:4996-4999) — "An expression against which to match mailbox names. '*' matches any number of characters in a mailbox name, and '%' matches similarly, but will not match across hierarchical boundaries."
- source:   docstring
- reading:  Only '*' and '%' are named as special. Every other character of the wildcard is therefore a literal that must match itself. A mailbox name containing '.', '+', '(' etc. must be matched literally; a wildcard with no '*'/'%' must select only the mailbox of that exact name. "%... will not match across hierarchical boundaries" rules out '%' matching a name that has a delimiter in the part '%' covers.
- claim:    For a literal wildcard w (no '*' or '%'), listMailboxes("", w) returns exactly the mailboxes whose name equals w (case-insensitively, since the account upper-cases names); a wildcard 'P%' never returns a name that has '/' after the prefix P.
- strength: Strongest form: exact-set equality against a reference matcher (fnmatch-like, written independently), not merely "the requested name is included".

## CLAIM-2
- evidence: — (wildcard comes from the client's LIST/LSUB argument, imap4.py:1450-1455, i.e. untrusted network input)
- source:   implicit
- reading:  Universal expectations: (a) any wildcard a client may send must not raise an undocumented exception (re.error) inside the server; (b) the cost of matching must be proportional to the input, not exponential in the wildcard length.
- claim:    wildcardToRegexp(w, "/") for any printable ASCII w returns a pattern without raising, and matching it against a mailbox name of length n completes in time polynomial (fast) in len(w)+n.
- strength: Stated for all printable ASCII wildcards, the alphabet arg_astring admits.

## CLAIM-3
- evidence: imap4.py:6109-6113 "Encode the given C{unicode} string using the IMAP4 specific variation of UTF-7." / imap4.py:6143-6146 "Decode the given L{str} using the IMAP4 specific variation of UTF-7."
- source:   structure (encoder/decoder pair registered as one codec)
- reading:  An encode/decode codec pair claims a round trip for every string the encoder accepts.
- claim:    s.encode("imap4-utf-7").decode("imap4-utf-7") == s for every str s (no lone surrogates).
- strength: Full equality, all non-surrogate text.

## CLAIM-4
- evidence: imap4.py:4605-4618 splitQuoted — "Tokens that would otherwise be separated but are surrounded by \" remain as a single token." ; _quote (imap4.py:4780) escapes '\\' and '"'.
- source:   structure (quote/split pair)
- reading:  _quote produces a quoted string; splitQuoted on that should yield back one token equal to the original.
- claim:    splitQuoted(_quote(b)) == [b] for printable bytes b without '\\'. (restricted: splitQuoted handles only \" escapes, not \\.)
- strength: Weakened to exclude backslash because splitQuoted's docstring documents only quote grouping, not backslash escapes.

## CLAIM-5
- evidence: imap4.py:4355-4369 parseIdList — "Parse a message set search key into a C{MessageSet}." ; MessageSet.__str__ produces "1:3,5"
- source:   structure (round trip str/parse)
- reading:  str(MessageSet) is the sequence-set syntax that parseIdList parses.
- claim:    parseIdList(str(ms).encode()) == ms for MessageSets built from positive int ranges.
- strength: Full equality.

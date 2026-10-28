# Claims for twisted.mail.imap4

All line numbers refer to src/twisted/mail/imap4.py in the checkout.

## CLAIM-1
- evidence: imap4.py:3313-3317 (IMAP4Client.list docstring) — "The pattern of mailbox names to match,
            optionally including either or both of the '*' and '%' wildcards.  '*' will match zero or
            more characters and cross hierarchical boundaries.  '%' will also match zero or more
            characters, but is limited to a single hierarchical level."
            and imap4.py:4996-4999 — `MemoryAccountWithoutNamespaces.listMailboxes` uses
            `wildcardToRegexp(wildcard, "/")` and `.match(i)` to implement that pattern on the server.
- source:   docstring + caller usage
- reading:  Only '*' and '%' are named as wildcards; every other character of the pattern is part
            of the mailbox name to match, i.e. literal. This rules out '.', '+', '(', '[', '?' etc.
            acting as metacharacters, and rules out a pattern being rejected because it is not a
            valid regex. It leaves open anchoring at the end (the server uses .match, prefix-anchored).
- claim:    For a wildcard with no '*'/'%', the compiled pattern matches a name N (via .match) only
            if N starts with the wildcard text (case-insensitively); and wildcardToRegexp never
            raises for any str wildcard.
- strength: Strongest form under the existing .match usage. I did not claim full-string anchoring
            because the caller uses .match and the docstring does not say "exactly".

## CLAIM-2
- evidence: —
- source:   implicit
- reading:  wildcardToRegexp builds a regex out of client-supplied LIST input. Every correct
            implementation must match in time roughly proportional to the input, otherwise a
            single LIST command stalls the reactor.
- claim:    listMailboxes(ref, wildcard) completes in bounded (sub-second) time for wildcards and
            mailbox names of a few dozen characters.
- strength: Bound chosen generously (1s) so that only super-polynomial blow-up fails.

## CLAIM-3
- evidence: imap4.py:6109-6176 — encoder: "Encode the given C{unicode} string using the IMAP4
            specific variation of UTF-7." decoder: "Decode the given L{str} using the IMAP4 specific
            variation of UTF-7."; registered as codec "imap4-utf-7" (6190-6201).
- source:   structure (encode/decode pair)
- reading:  A codec pair claims a round trip for every str the encoder accepts.
- claim:    s.encode("imap4-utf-7").decode("imap4-utf-7") == s for every str s, and the encoded
            form contains only printable ASCII 0x20-0x7e (RFC 3501 5.1.3).
- strength: Full round trip, plus the output alphabet stated in RFC 3501 which this codec names.

## CLAIM-4
- evidence: imap4.py:4355-4369 — parseIdList: "Parse a message set search key into a C{MessageSet}."
            "A string description of an id list, for example "1:3, 4:*"", and MessageSet.__str__
            (399-411) produces the sequence-set syntax.
- source:   structure (parse/format pair) + docstring
- reading:  str(MessageSet) emits the sequence-set syntax that parseIdList parses; parsing it back
            must yield the same set.
- claim:    For a MessageSet m built from positive ints (no '*'), parseIdList(str(m).encode()) == m.
- strength: Equality of normalized ranges, the strongest form.

## CLAIM-5
- evidence: imap4.py:146-155 — "The range is inclusive and unordered ... C{Message(2, 1)} is
            equivalent to C{MessageSet(1, 2)}, and both describe messages 1 and 2."
            and clean(): "Clean ranges list, combining adjacent ranges".
- source:   docstring
- reading:  The set denotes a set of integers; len, iteration, membership and the reference
            python set must agree.
- claim:    For MessageSets built by adding ranges of positive ints, set(iter(m)) equals the union
            of the inclusive ranges, len(m) == len(that union), and `x in m` agrees.
- strength: Reference-model comparison, strongest form.

## CLAIM-6
- evidence: imap4.py:4838-4853 — collapseNestedLists: "Turn a nested list structure into an
            s-exp-like string. Strings ... will be sent as literals if they contain CR or LF,
            otherwise they will be quoted." and parseNestedParens (4720-4731): "Parse an s-exp-like
            string into a more useful data structure."
- source:   structure (format/parse pair)
- reading:  The two are the server's serializer and client's parser of the same s-exp syntax.
- claim:    For nested lists of bytes, parseNestedParens(collapseNestedLists(x)) == x.
- strength: Full round trip.

## CLAIM-7
- evidence: imap4.py:4605-4620 — splitQuoted: "Tokens that would otherwise be separated but are
            surrounded by \" remain as a single token."
- source:   docstring
- reading:  A quoted token produced by _quote (which escapes \ and ") must come back as exactly one
            token equal to the original.
- claim:    splitQuoted(_quote(b)) == [b] for bytes b of printable ASCII.
- strength: Exact equality.

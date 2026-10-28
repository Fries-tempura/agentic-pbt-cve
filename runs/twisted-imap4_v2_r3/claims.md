# Claims for twisted.mail.imap4

## CLAIM-1
- evidence: src/twisted/mail/interfaces.py:983-986 (IAccount.listMailboxes) — "An expression against which to match mailbox names. '*' matches any number of characters in a mailbox name, and '%' matches similarly, but will not match across hierarchical boundaries."
- source:   docstring
- reading:  Only '*' and '%' are named as special, so every other character in the wildcard stands for itself. "Matches" means the wildcard describes the whole name (RFC 3501 6.3.8 LIST semantics, which this method implements for the LIST/LSUB commands). '%' must not cover the hierarchy delimiter ('/' in MemoryAccount). Matching is case-insensitive here because MemoryAccount upper-cases all names.
- claim:    MemoryAccount.listMailboxes("", w) returns exactly the mailbox names that the glob w matches, where '*' = any string, '%' = any string with no '/', and every other character matches itself, case-insensitively.
- strength: Strongest form: exact set equality against a reference matcher. A weaker form ("every '*' wildcard returns everything") would miss both the literal-character and the anchoring questions.

## CLAIM-2
- evidence: —
- source:   implicit
- reading:  The wildcard is the client-supplied argument of LIST/LSUB (IMAP4Server._listWork passes it straight through). Any string a client can send is valid input to listMailboxes; it must not raise an undocumented exception (re.error).
- claim:    listMailboxes("", w) returns a list for every text wildcard w.
- strength: Must-not-crash; the full answer is CLAIM-1.

## CLAIM-3
- evidence: —
- source:   implicit
- reading:  listMailboxes builds a regex from the client's wildcard (wildcardToRegexp). The cost of a LIST must scale with the wildcard and mailbox name lengths, not exponentially/polynomially in the number of wildcards.
- claim:    listMailboxes("", w) with |w| <= ~40 against a short mailbox name completes in well under a second.
- strength: A bound, not an exact complexity class.

## CLAIM-4
- evidence: imap4.py:6109-6175 encoder/decoder, registered as codec "imap4-utf-7"; docstrings "Encode the given unicode string using the IMAP4 specific variation of UTF-7" / "Decode ..."
- source:   structure
- reading:  An encode/decode codec pair claims a round trip for all str input. Encoder output must be 7-bit printable (RFC 3501 5.1.3).
- claim:    s.encode("imap4-utf-7").decode("imap4-utf-7") == s, and the encoded bytes are all in 0x20..0x7E.
- strength: Strongest.

## CLAIM-5
- evidence: imap4.py:4355-4369 parseIdList docstring "@return: A MessageSet that contains the ids defined in the list"; MessageSet.__str__ produces "a:b,c" sequence-set syntax.
- source:   docstring + structure
- reading:  str(MessageSet) emits RFC 3501 sequence-set; parseIdList parses it back. Round trip.
- claim:    parseIdList(str(ms).encode()) == ms for MessageSets of positive ints.
- strength: Strongest.

## CLAIM-6
- evidence: imap4.py:4838-4860 collapseNestedLists docstring "Turn a nested list structure into an s-exp-like string. Strings ... will be sent as literals if they contain CR or LF, otherwise they will be quoted"; parseNestedParens docstring "Parse an s-exp-like string ... A list containing the tokens present in the input."
- source:   structure
- reading:  Serializer / parser pair for the same s-exp grammar.
- claim:    parseNestedParens(collapseNestedLists(x)) == x for nested lists of non-empty printable-ASCII bytes.
- strength: Restricted to the quoted path; literal path and NIL excluded.

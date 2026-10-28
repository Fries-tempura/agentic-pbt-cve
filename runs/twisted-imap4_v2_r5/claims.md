# Claims for twisted.mail.imap4

## CLAIM-1
- evidence: imap4.py:6109-6155 — encoder: "Encode the given C{unicode} string using the IMAP4 specific variation of UTF-7."; decoder: "Decode the given L{str} using the IMAP4 specific variation of UTF-7."
- source:   structure
- reading:  An encoder/decoder pair registered as a single codec ("imap4-utf-7") claims a round trip. Mailbox names are encoded by the client (`_prepareMailboxName`) and decoded by the server (`_parseMbox`), so any str the encoder accepts must come back unchanged.
- claim:    For every str s, `s.encode("imap4-utf-7").decode("imap4-utf-7") == s`.
- strength: Strongest form; no restriction on code points stated.

## CLAIM-2
- evidence: imap4.py:6109 (RFC 3501 §5.1.3 modified UTF-7, referenced as "IMAP4 specific variation of UTF-7")
- source:   reference
- reading:  RFC 3501 §5.1.3 requires the encoded mailbox name to consist only of printable US-ASCII (0x20-0x7e).
- claim:    Every byte of `s.encode("imap4-utf-7")` is in 0x20..0x7e.
- strength: Strongest form.

## CLAIM-3
- evidence: imap4.py:146-157 — "The range is inclusive and unordered ... so that C{Message(2, 1)} is equivalent to C{MessageSet(1, 2)}, and both describe messages 1 and 2."
- source:   docstring
- reading:  A MessageSet built from ints describes exactly the union of the inclusive ranges given; ordering of endpoints does not matter. Iteration, `in`, and `len` must all agree with that set.
- claim:    For ranges of positive ints, `set(ms) == union of ranges`, `len(ms) == len(that set)`, and `x in ms` iff x is in the union.
- strength: Strongest form (exact set equality, not just subset).

## CLAIM-4
- evidence: imap4.py:4357-4367 — parseIdList: "Parse a message set search key into a C{MessageSet}" / "A C{MessageSet} that contains the ids defined in the list"
- source:   docstring + structure
- reading:  `str(MessageSet)` emits the RFC 3501 sequence-set syntax and parseIdList parses it; so they form a round trip.
- claim:    `parseIdList(str(ms).encode()) == ms` for MessageSets built from positive ints (and `*`).
- strength: Strongest form.

## CLAIM-5
- evidence: imap4.py:4838-4843 — collapseNestedLists: "Turn a nested list structure into an s-exp-like string. Strings in C{items} will be sent as literals if they contain CR or LF, otherwise they will be quoted." ; imap4.py:4720 parseNestedParens: "Parse an s-exp-like string into a more useful data structure."
- source:   caller usage / structure
- reading:  The server formats responses with collapseNestedLists; the client (Command.finish, imap4.py:556) parses them with parseNestedParens. They are inverses for nested lists of bytes.
- claim:    `parseNestedParens(collapseNestedLists(x)) == x` for nested lists of non-empty bytes (no None).
- strength: Restricted to bytes without CR/LF first (quoted path); literal path tested separately as part of same claim.

## CLAIM-6
- evidence: imap4.py:3309-3315 (IMAP4Client.list) — "'*' will match zero or more characters and cross hierarchical boundaries. '%' will also match zero or more characters, but is limited to a single hierarchical level." ; interfaces.py:982-986 — listMailboxes "wildcard: An expression against which to match mailbox names. '*' matches any number of characters in a mailbox name, and '%' matches similarly"
- source:   docstring
- reading:  Only `*` and `%` are special; every other character in the wildcard is a literal character of the mailbox name. A wildcard containing no `*`/`%` therefore matches only the identical (case-insensitive) name, and never raises.
- claim:    `MemoryAccount.listMailboxes("", w)` does not raise for any str w, and for a w with no wildcards it returns exactly the mailbox whose name equals w (case-insensitively).
- strength: Strongest form.

## CLAIM-7
- evidence: —
- source:   implicit
- reading:  Must not hang: wildcardToRegexp compiles client-supplied text into a regex and matches it against mailbox names; cost must stay roughly linear in input size.
- claim:    listMailboxes with a wildcard of length ≤ ~100 and mailbox names of length ≤ ~100 completes in well under a second.
- strength: Bound is generous.

## CLAIM-8
- evidence: imap4.py:4605-4618 — splitQuoted: "Tokens that would otherwise be separated but are surrounded by \" remain as a single token. Any token that is not quoted and is equal to \"NIL\" is tokenized as L{None}."
- source:   docstring
- reading:  Joining whitespace-free atoms with spaces and quoting arbitrary quote-free tokens gives back exactly those tokens; a quoted "NIL" stays bytes.
- claim:    `splitQuoted(b" ".join(_quote(t) for t in toks)) == toks` for tokens without `"` or `\\`.
- strength: Excludes escapes since the docstring says nothing about escaping.

## Amendments after testing
- CLAIM-5: the strategy generates arbitrary bytes including `\` and `"`; collapseNestedLists escapes both via `_quote`, so the round trip must hold for them as well. RFC 3501 §9 (`quoted-specials`) confirms `\\` means a single backslash.
- CLAIM-6: the test's failure on `w='.'` comes from regex injection. The same test also shows that `listMailboxes` uses `re.match`, so a plain wildcard `INBOX` also returns `INBOXES` (it matches as a prefix).

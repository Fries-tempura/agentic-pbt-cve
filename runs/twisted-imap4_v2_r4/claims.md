# Claims for twisted.mail.imap4

Source file: src/twisted/mail/imap4.py (Twisted 26.4.0.post0)

## CLAIM-1
- evidence: imap4.py:6109-6115 — encoder: "Encode the given C{unicode} string using the IMAP4 specific variation of UTF-7."; decoder (6143-6147): "Decode the given L{str} using the IMAP4 specific variation of UTF-7."; registered as a codec pair via `codecs.CodecInfo(encoder, decoder, ...)` (6187).
- source:   docstring + structure (encode/decode codec pair)
- reading:  A registered codec whose encoder accepts any `str` and does not document a lossy
            policy ("errors ... Currently ignored", so no 'replace'/'ignore' mode) claims that
            decoding its output recovers the input. Modified UTF-7 (RFC 3501 §5.1.3) can
            represent every Unicode string, so nothing in the format forces loss.
- claim:    For every str s, s.encode("imap4-utf-7").decode("imap4-utf-7") == s.
- strength: Strongest form. A weaker form ("round trip for printable ASCII") passed over: the
            docstring says "the given unicode string", no restriction.

## CLAIM-2
- evidence: imap4.py:4838-4858 — collapseNestedLists: "Turn a nested list structure into an
            s-exp-like string. Strings in C{items} will be sent as literals if they contain CR
            or LF, otherwise they will be quoted."; parseNestedParens (4720-4731): "Parse an
            s-exp-like string into a more useful data structure. @return: A list containing the
            tokens present in the input."
- source:   structure (serializer/parser pair for the same s-exp syntax)
- reading:  Server serializes with collapseNestedLists, client parses with parseNestedParens.
            Quoted strings / literals carry arbitrary byte strings, so a byte string must come
            back as the same token, and nesting must be preserved.
- claim:    For nested lists of non-empty bytes (excluding the literal b"NIL"),
            parseNestedParens(collapseNestedLists(x)) == x.
- strength: Restricted to bytes leaves (ints/None change type by design: ints become
            bytes, None becomes NIL). Empty bytes excluded only if the parser maps "" oddly
            — kept in, see test.
- amended:  While testing, a literal at the very end of the input whose content ends in
            whitespace was truncated by the leading `s.strip()` in parseNestedParens. Real
            server responses never end with a literal (they close with ")" or continue on a
            later line), so leaves are restricted to values without trailing whitespace. The
            backslash failure is unaffected by this restriction.

## CLAIM-3
- evidence: imap4.py:146-152 — "A L{MessageSet} can describe a range of identifiers, e.g.
            C{MessageSet(1, 2)}. The range is inclusive and unordered ... both describe
            messages 1 and 2"; 159-162 "constructed by addition".
- source:   docstring
- reading:  A MessageSet built by adding ranges contains exactly the union of those inclusive
            ranges; iteration yields them, len counts them, `in` tests them.
- claim:    For ranges of positive ints, set(ms) == union of ranges, len(ms) == size of union,
            and `v in ms` agrees with the union.
- strength: Strongest form.

## CLAIM-4
- evidence: imap4.py:4355-4369 — parseIdList: "Parse a message set search key into a
            C{MessageSet}." / "@return: A C{MessageSet} that contains the ids defined in the list"
- source:   docstring + structure (str(MessageSet) produces the sequence-set syntax)
- reading:  parseIdList(str(ms)) must describe the same ids as ms.
- claim:    parseIdList(str(ms).encode()) == ms for MessageSets of positive ints.
- strength: Strongest form.

## CLAIM-5
- evidence: —
- source:   implicit (must not hang)
- reading:  parseIdList is fed client-controlled sequence sets (arg_seqset, and once per
            message per term in __cbManualSearch / search_UID). Parsing a comma-separated list
            should cost time proportional to the number of parts.
- claim:    Doubling the number of comma-separated parts roughly doubles parse time (not 4x).
- strength: Implicit; asserted as a ratio bound, not an absolute time.

## CLAIM-6
- evidence: imap4.py:4720-4731 — "@raise MismatchedNesting: Raised if the number or placement
            of opening or closing parenthesis is invalid."
- source:   docstring (@raise) + implicit (must not crash)
- reading:  The only documented exception is MismatchedNesting, and only for invalid nesting.
            Well-nested input of any depth that fits in a line is valid.
- claim:    For balanced parentheses of any depth, parseNestedParens returns a list and raises
            nothing.
- strength: Strongest form.

## CLAIM-7
- evidence: imap4.py:4508-4511 (Query docstring) — "The given date should be a string in the
            format of 'DD-Mon-YYYY'. For example, '03-Mar-2003'."; parseTime regex 6082-6086.
- source:   docstring + structure
- reading:  parseTime parses that format into a struct_time with the same day/month/year.
- claim:    parseTime("%02d-%s-%04d" % (d, Mon, y)) has tm_mday == d, tm_mon == month index,
            tm_year == y.
- strength: Strongest form for well-formed input.

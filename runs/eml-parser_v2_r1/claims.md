# Claims for eml_parser.parser

## CLAIM-1
- evidence: parser.py:144 — "ignore_bad_start (bool, optional): Ignore invalid file start." and parser.py:225 — "# Skip invalid start of file"
- source:   docstring / comment
- reading:  The flag only skips an *invalid* start (leading lines that are not headers). A file whose
            first line is already a header has no invalid start, so nothing should be skipped or altered.
            The rest of the file is to be kept as-is; nothing suggests line structure is changed.
- claim:    For a well-formed email (first line is a `Name: value` header), decode_email_bytes(x,
            ignore_bad_start=True) parses the same headers/body as decode_email_bytes(x).
- strength: Strongest form: identical parsed header values and body content. (Weaker "does not crash" passed over.)

## CLAIM-2
- evidence: parser.py:144 — "ignore_bad_start (bool, optional): Ignore invalid file start."
- source:   docstring
- reading:  If leading junk lines (no ':') precede a valid email, they are dropped and the remaining
            email is parsed as if the junk were absent.
- claim:    decode_email_bytes(junk + x, ignore_bad_start=True) yields the same headers as decode_email_bytes(x).
- strength: Strongest form; equality of header dict.

## CLAIM-3
- evidence: parser.py:653-662 — "Yield a more or less constant slice of a large string. ... we try our best to enlarge the window as to not cut off URLs"
- source:   docstring
- reading:  Slices are used in place of the whole body for regex search (parser.py:468-471), so every
            character of the body must appear in some slice; losing text would silently lose IOCs.
- claim:    Every index of body is covered by at least one yielded slice (slices are contiguous
            substrings at known offsets).
- strength: Coverage only; "URLs never cut" is stated as best effort ("try our best") so not claimed.

## CLAIM-4
- evidence: parser.py:944-955 — "Hash type to use, can be any of 'md5', 'sha1', 'sha256', 'sha512'." ; raise ValueError
- source:   docstring / reference (hashlib)
- reading:  Result equals hashlib.<type>(value as utf-8).hexdigest(); other types raise ValueError.
- claim:    get_hash(v, t) == hashlib.new(t, v_bytes).hexdigest() for allowed t; ValueError otherwise.
- strength: Full reference comparison.

## CLAIM-5
- evidence: parser.py:714-721 — "Returns a string of the validated IP address or the host."
- source:   docstring / reference (ipaddress)
- reading:  For an IP address input (no force_routable) the returned value is the canonical IP string.
- claim:    get_valid_domain_or_ip(str(ip)) == str(ip) for any ipaddress IPv4/IPv6 address.
- strength: Full.

## CLAIM-6
- evidence: parser.py:821-828 — "Parses a given header field with e-mail addresses to a list of e-mail addresses."; parser.py:859 lower()
- source:   docstring / reference (email.utils.getaddresses)
- reading:  Every address in the To header is returned, lowercased, in order.
- claim:    For To: a1, a2, ... with simple addresses, headeremail2list('to') == [a.lower() for a in addrs].
- strength: Full equality.

## CLAIM-7
- evidence: —
- source:   implicit
- reading:  decode_email_bytes accepts arbitrary bytes ("Some intelligence is applied while parsing the
            file in order to work around broken files"). It must not raise undocumented exceptions.
            RecursionError is documented for nesting > MULTIPART_RECURSION_LIMIT.
- claim:    decode_email_bytes(b) returns a dict or raises RecursionError, for any bytes b.
- strength: Full.

## CLAIM-8
- evidence: — (parser.py:468 comment: "If we start directly a findall on 500K+ body we got time and memory issues")
- source:   implicit (cost)
- reading:  The author explicitly cares about regex cost on bodies, and header regexes run unsliced.
            Cost must scale ~linearly with input size.
- claim:    Parsing an email with an n-char body or header line takes time roughly O(n); doubling n
            does not quadruple time.
- strength: Bounded-time check on adversarial-but-plausible strings (long runs of URL/domain/local-part chars).

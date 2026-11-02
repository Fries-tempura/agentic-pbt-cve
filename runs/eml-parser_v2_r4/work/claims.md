# Claims for eml_parser.parser

## CLAIM-1
- evidence: parser.py:195/218 — "ignore_bad_start: Ignore invalid file start for this run."; parser.py:225 — "# Skip invalid start of file"; parser.py:232 — `if start and b':' not in line: continue`
- source:   docstring + structure
- reading:  The flag only *skips* the invalid start (leading lines with no ':'); everything from the
            first header-looking line onward is the e-mail and must be parsed as such. Nothing is said
            about altering the remaining lines. Rules out: merging lines, changing headers of an email
            that has no invalid start at all.
- claim:    For a well-formed e-mail E and a prefix P of lines containing no ':',
            decode_email_bytes(P+E, ignore_bad_start=True) yields the same headers as decode_email_bytes(E).
            In particular with P empty the flag changes nothing.
- strength: Strongest form: equality of parsed headers (from/to/subject/raw header dict). Body uuids/
            hashes excluded only because uuids differ per call.

## CLAIM-2
- evidence: —
- source:   implicit
- reading:  Parsing cost must scale ~linearly with input. The author explicitly cares (parser.py:468
            "If we start directly a findall on 500K+ body we got time and memory issues..."), but the
            Received-header path runs findall on the whole unbounded line (parser.py:404).
- claim:    Doubling the length of a Received header increases decode_email_bytes time by ~2x, not ~4x;
            a 64 KB header parses in well under a second.
- strength: Bounded ratio test (ratio < 3 when doubling), plus absolute bound.

## CLAIM-3
- evidence: parser.py:945 — "Generate a hash of type *hash_type* for a given value." / "Returns the calculated hash as a string."; parser.py:954-955 raises ValueError on other types
- source:   docstring + assertion
- reading:  str is utf-8 encoded then hashed; result is the hex digest of hashlib's algorithm.
- claim:    get_hash(v, t) == hashlib.new(t, v_bytes).hexdigest() for t in md5/sha1/sha256/sha512; any other t raises ValueError.
- strength: Full reference equality.

## CLAIM-4
- evidence: parser.py:715-721 — "Function to determine if an IP address, Email address, or Domain is valid." "Returns a string of the validated IP address or the host."
- source:   docstring
- reading:  For an IP (optionally as user@ip or [ip]) with ip_force_routable off, the IP is valid and is returned as a string.
- claim:    get_valid_domain_or_ip(str(ip)) == str(ip) and get_valid_domain_or_ip(f"x@[{ip}]") == str(ip).
- strength: Exact equality with ipaddress reference.

## CLAIM-5
- evidence: parser.py:822-828 — "Parses a given header field with e-mail addresses to a list of e-mail addresses." / "Returns a list of strings which represent e-mail addresses."; parser.py:859 `.lower()`
- source:   docstring + structure
- reading:  Each address in To becomes one lowercase addr-spec, in order.
- claim:    For To: a1, a2, ... (simple local@domain addresses), headeremail2list('to') == [a.lower() for a in addrs].
- strength: Exact list equality.

## CLAIM-6
- evidence: —
- source:   implicit
- reading:  decode_email_bytes documents no exceptions; "Some intelligence is applied while parsing the file in order to work around broken files."
- claim:    decode_email_bytes(b) returns a dict for any bytes b built from header/body fragments.
- strength: Only RecursionError for >100 nesting is documented (get_raw_body_text Raises); excluded.

## CLAIM-7
- evidence: parser.py:653 — "Yield a more or less constant slice of a large string."; parser.py:471 caller scans every slice for URLs/e-mails of the whole body
- source:   docstring + caller usage
- reading:  The slices are pieces of the body; the caller relies on them jointly covering the body so nothing is skipped.
- claim:    Every index of body lies inside at least one yielded slice (the slices, located in order, cover body).
- strength: Coverage, not exact partition (overlaps are documented: "rewind the window by 16 characters").

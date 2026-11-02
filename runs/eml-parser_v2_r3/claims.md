# Claims for eml_parser.parser

## CLAIM-1
- evidence: parser.py:144/218 — "ignore_bad_start (bool, optional): Ignore invalid file start." / "ignore_bad_start: Ignore invalid file start for this run."
- source:   docstring
- reading:  The flag only *ignores an invalid start*. It promises nothing changes for a file whose
            start is already valid (first line is a header `Name: value`). It rules out altering
            the rest of the message (line structure, headers, body).
- claim:    For a well-formed email, decode_email_bytes(raw, ignore_bad_start=True) returns the same
            subject/from/to/body hashes as decode_email_bytes(raw).
- strength: Strongest the evidence supports for valid input. A weaker form ("doesn't crash") would
            pass on an implementation that destroys the message.

## CLAIM-2
- evidence: parser.py:144 — "ignore_bad_start (bool, optional): Ignore invalid file start."
- source:   docstring
- reading:  If junk lines (without ':') precede a well-formed email, enabling the flag must make the
            result equal to parsing the email without the junk.
- claim:    decode_email_bytes(junk + raw, ignore_bad_start=True) headers == decode_email_bytes(raw) headers.
- strength: Full equality of the extracted subject/from/to.

## CLAIM-3
- evidence: parser.py:145-147 — "email_force_tld (bool, optional): Only match e-mail addresses with a TLD ... By default this is disabled."
- source:   docstring
- reading:  The option is a constructor argument of one EmlParser instance; "by default disabled"
            means an instance built with the default does match `john@doe`, irrespective of other
            instances created earlier.
- claim:    For any sequence of constructions, an EmlParser() built with email_force_tld=False
            reports TLD-less addresses in received headers (received_email) just like a fresh process.
- strength: Sequence claim (order of operations); per-instance configuration.

## CLAIM-4
- evidence: parser.py:653-664 — "Yield a more or less constant slice of a large string ... we try our best to enlarge the window as to not cut off URLs."
- source:   docstring / structure
- reading:  Slicing is an optimisation to bound regex cost; the slices are the only text later
            scanned for URLs/emails/IPs. An optimisation must not discard text: every character of
            the body must appear in at least one slice.
- claim:    Every character position of body is contained in some yielded slice.
- strength: Coverage only (not exact partition, since rewinding produces deliberate overlap).

## CLAIM-5
- evidence: —
- source:   implicit
- reading:  Universal expectation: no crash on an input the API accepts. decode_email_bytes accepts
            any bytes of an e-mail ("Some intelligence is applied while parsing the file in order to
            work around broken files", parser.py:188).
- claim:    decode_email_bytes does not raise on syntactically plausible emails built from headers
            with arbitrary printable values.
- strength: n/a

## CLAIM-6
- evidence: parser.py:468-470 — "If we start directly a findall on 500K+ body we got time and memory issues..."; plus implicit cost expectation.
- source:   implicit
- reading:  Parsing cost must scale ~linearly with input size, both for header fields (Received) and
            bodies. The author explicitly guards bodies; headers carry the same regexes.
- claim:    Doubling the size of a header/body built from the regexes' special characters at most
            ~roughly doubles run time (no quadratic blow-up).
- strength: Assert ratio bound, not absolute time.

# Claims for eml_parser.parser

## CLAIM-1
- evidence: parser.py:144 — "ignore_bad_start (bool, optional): Ignore invalid file start. This has a considerable performance impact."; parser.py:225 — "# Skip invalid start of file"
- source:   docstring, comment
- reading:  The option only *skips* leading garbage before the first header line. It says nothing
            about changing how a well-formed message is parsed. If the file already starts with
            a header line there is no invalid start, so nothing should be skipped and nothing
            else should change.
- claim:    For a well-formed message (first line is a header), decode_email_bytes(raw,
            ignore_bad_start=True) gives the same from/to/subject/headers/body as
            decode_email_bytes(raw).
- strength: Strongest form: full equality of the parsed header fields and body content. A weaker
            form ("does not crash") would pass even if the message were mangled.

## CLAIM-2
- evidence: parser.py:145-147 — "email_force_tld (bool, optional): Only match e-mail addresses with a TLD, i.e. exclude something like john@doe. ... By default this is disabled."
- source:   docstring, structure (constructor argument stored per instance: `self.email_force_tld = email_force_tld`)
- reading:  It is a constructor argument, so it configures *that* parser. "By default this is
            disabled" means a parser built without it matches john@doe. Nothing suggests that
            building one parser changes the behaviour of others.
- claim:    A parser built with default arguments reports `john@doe` found in a body, whether or
            not another EmlParser(email_force_tld=True) was built earlier.
- strength: Stated as an ordering claim (independent of construction history), which is the
            strongest form the per-instance argument supports.

## CLAIM-3
- evidence: parser.py:403-408 — "# search for e-mail addresses ... headers_struc['received_email'] += [mail_candidate]"; get_valid_domain_or_ip docstring parser.py:720 — "Returns a string of the validated IP address or the host."
- source:   comment, structure
- reading:  The key is `received_email` and the comment says it collects e-mail addresses. With
            email_force_tld the candidate is replaced by get_valid_domain_or_ip's return value,
            which its own docstring says is the *host*. The force_tld option is documented only as
            a filter ("Only match e-mail addresses with a TLD"), not as changing what is stored.
- claim:    With email_force_tld=True, every entry in header['received_email'] is an e-mail
            address (contains '@'), the same entry the default parser would report.
- strength: Strongest form: entries are the full addresses. Not just "non-empty".

## CLAIM-4
- evidence: parser.py:653-662 — "Yield a more or less constant slice of a large string. ... we try our best to enlarge the window as to not cut off URLs ... in order to return a maximum possible correct URLs."
- source:   docstring, caller usage (parse_email scans every slice for URLs/emails/IPs, parser.py:471)
- reading:  The slices replace a full scan of the body, so together they must cover the whole
            body; otherwise content is silently skipped. Overlap is allowed (rewind by 16).
- claim:    Every character index of body is contained in at least one yielded slice, and the
            generator terminates.
- strength: Coverage of every index is the strongest form the docstring supports; exact
            partition is not claimed (rewinds overlap deliberately).

## CLAIM-5
- evidence: parser.py:945-952 — "Generate a hash of type *hash_type* for a given value. ... hash_type: Hash type to use, can be any of 'md5', 'sha1', 'sha256', 'sha512'."
- source:   docstring, reference (hashlib)
- reading:  For str, the code encodes UTF-8; the result must equal hashlib's hexdigest.
- claim:    get_hash(v, t) == hashlib.new(t, v_bytes).hexdigest(); str hashes as its UTF-8 bytes.
- strength: Full equality against the reference.

## CLAIM-6
- evidence: parser.py:715-721 — "Function to determine if an IP address, Email address, or Domain is valid. ... Returns a string of the validated IP address or the host."
- source:   docstring, reference (ipaddress)
- reading:  For a valid IP (optionally after `user@`), with ip_force_routable off, the return is
            the IP in canonical form.
- claim:    get_valid_domain_or_ip(str(ip)) == str(ip) and get_valid_domain_or_ip('x@'+str(ip)) == str(ip).
- strength: Full equality.

## CLAIM-7
- evidence: —
- source:   implicit (cost must scale with input). Also parser.py:468 — "If we start directly a findall on 500K+ body we got time and memory issues..." shows the author treats
            super-linear regex cost on untrusted input as a defect.
- reading:  decode_email_bytes processes untrusted e-mail. Its time should grow roughly linearly
            with header length; a 2x longer Received header should cost ~2x, not ~4x.
- claim:    decode_email_bytes on a message with a Received header of n chars runs in time ~O(n).
- strength: Assert a ratio bound when doubling n (allowing generous slack, < 3x).

## CLAIM-8
- evidence: parser.py:187-188 — "Some intelligence is applied while parsing the file in order to work around broken files."
- source:   docstring, implicit (no undocumented exceptions)
- reading:  Malformed input is expected; no Raises section documents an exception except
            RecursionError for deep nesting.
- claim:    decode_email_bytes does not raise on header/body text built from e-mail-like pieces.
- strength: Only no-crash; the docstring promises nothing more concrete about broken input.

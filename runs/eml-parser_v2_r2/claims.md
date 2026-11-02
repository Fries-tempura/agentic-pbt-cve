# Claims for `eml_parser.parser`

Source: `dataset/checkouts/CVE-2026-55618__eml-parser/eml_parser/parser.py`

## CLAIM-1
- evidence: parser.py:144 / :195 / :218 — "ignore_bad_start (bool, optional): Ignore invalid file start." and
            parser.py:225 — "# Skip invalid start of file"
- source:   docstring, comment
- reading:  The option promises to *skip* leading lines that are not a valid start (lines without ':'),
            and nothing else. Skipping a prefix implies the rest of the file is passed through unchanged.
            Two consequences: (a) on a file that already starts validly there is nothing to skip, so the
            option must not change the parse; (b) on a file with junk lines before the first header, the
            parse must equal the parse of the file with the junk removed. It is documented as costing
            performance, never as changing results.
- claim:    For a well-formed e-mail E and any prefix J of lines containing no ':',
            decode_email_bytes(J+E, ignore_bad_start=True) has the same headers and body as
            decode_email_bytes(E) (ignoring per-run uuids).
- strength: Strongest form; (a) is the special case J = empty.

## CLAIM-2
- evidence: parser.py:971 — "counter (int, optional): A counter which is used for generating attachments
            file-names in case there are none found in the header." ; parser.py:1046 `filename = f'part-{counter:03d}'`;
            parser.py:1087 `counter += 1`
- source:   docstring, structure
- reading:  A *counter* used to generate names means each unnamed attachment gets the next number; the
            code itself increments it after each attachment. The purpose of a counter is to make the
            generated names distinguish attachments.
- claim:    In a multipart message with N attachments that carry no filename, the reported attachment
            filenames are N distinct names (part-000, part-001, ...).
- strength: Strongest form supported. I do not claim the exact numbering order, only distinctness.

## CLAIM-3
- evidence: parser.py:653-664 — "Yield a more or less constant slice of a large string. ... In case we find a
            *://* at the first 8 characters of a sliced body window, we rewind the window ... If we find the same
            string at the end of a sliced body window we try to look for invalid URL characters up to
            *max_distance* length ... This is done in order to return a maximum possible correct URLs."
- source:   docstring
- reading:  The slicer is an optimisation of "run the regex over the whole body". It may overlap windows,
            but it must not lose text, and it explicitly promises that URLs straddling a window border are
            not cut (as long as they are shorter than max_distance=100 and the scheme <= 8 chars).
- claim:    (a) every character of the body lies in at least one yielded slice; (b) a short URL
            (`http://` + host + path, < 60 chars, delimited by spaces) placed anywhere in a long body is
            reported intact in the body's `uri` list by parse_email.
- strength: (b) is weaker than "same result as a single findall over the body" — I passed over that because
            the docstring only commits to URLs, and only to "maximum possible".

## CLAIM-4
- evidence: parser.py:715-721 — "Function to determine if an IP address, Email address, or Domain is valid. ...
            Returns: str: Returns a string of the validated IP address or the host."
- source:   docstring, reference (ipaddress)
- reading:  For an IP address (bare or as the host part of an e-mail) the return is the IP in canonical
            string form, with ip_force_routable False.
- claim:    For any IPv4/IPv6 address a, get_valid_domain_or_ip(str(a)) == str(a) and
            get_valid_domain_or_ip('x@' + str(a)) == str(a).
- strength: Full.

## CLAIM-5
- evidence: parser.py:822-828 — "Parses a given header field with e-mail addresses to a list of e-mail addresses."
- source:   docstring, reference (email.utils.getaddresses), structure (`.lower()` at :859)
- reading:  The result is the list of addr-specs in the header, lower-cased.
- claim:    For a To header built from simple addresses, headers['to'] == [a.lower() for a in addresses].
- strength: Full for the simple-address domain.

## CLAIM-6
- evidence: —
- source:   implicit
- reading:  decode_email_bytes accepts arbitrary bytes ("Some intelligence is applied while parsing the file
            in order to work around broken files"). The only documented exception is RecursionError (nesting).
- claim:    decode_email_bytes(b) does not raise for header-like/body-like random byte inputs.
- strength: —

## CLAIM-7
- evidence: — (parser.py:468 comment: "If we start directly a findall on 500K+ body we got time and memory issues...")
- source:   implicit
- reading:  Parsing cost must scale (near-)linearly with input. The authors acknowledge regex cost on bodies
            and window them, but Received headers are run through email/ip/domain regexes unwindowed.
- claim:    decode_email_bytes on a message whose Received header has length n runs in time roughly linear
            in n (doubling n does not ~quadruple time); a 100 KB header parses in well under a second.
- strength: —

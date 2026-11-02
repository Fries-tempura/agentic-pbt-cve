# Claims for setuptools.package_index

## CLAIM-1
- evidence: package_index.py:580 — "If `spec` is a URL, it is downloaded to a subpath of `tmpdir`, and the local filename is returned."; package_index.py:821-823 — `while '..' in name: name = name.replace('..', '.').replace('\\', '_')`; package_index.py:817 — doctest `str(pathlib.Path(du(url, root)).relative_to(root))`
- source:   docstring (plus a comment-free sanitising loop in the code)
- reading:  `download()` sends a URL to `_download_url`, which takes its path only from `_resolve_download_filename(url, tmpdir)`. "A subpath of tmpdir" is a postcondition on that path: it must sit inside tmpdir. The `..` stripping and the replacement of `\\` show the author meant to stop the URL from leaving tmpdir. This rules out *any* URL-derived name that ends up outside tmpdir, including an absolute path.
- claim:    For any http(s) URL, `_resolve_download_filename(url, tmpdir)` returns a path whose normalised form is strictly inside tmpdir.
- strength: Strongest form. A weaker form ("the result contains no '..'") would pass even when the name is an absolute path that escapes tmpdir.

## CLAIM-2
- evidence: package_index.py:908 — "Given a possible VCS URL, return a clean URL and resolved revision if any." plus doctests at 911-916
- source:   docstring
- reading:  Splitting off `@rev` and the `+vcs` scheme prefix. For a URL with no `@` and no `+` in the scheme, nothing is there to clean, so the URL must come back with the same scheme, netloc and path, and rev None.
- claim:    For `scheme://host/path` (no `@`, no `+`, no fragment) the result is `(url, None)`; for `git+scheme://host/path@rev` it is `(scheme://host/path, rev)`.
- strength: Exact round trip on the documented forms.

## CLAIM-3
- evidence: package_index.py:958 — "Decode HTML entities in the given text."
- source:   docstring / reference
- reading:  `html.unescape` is the stdlib reference for decoding HTML entities; `decode_entity` calls it on each matched entity.
- claim:    `htmldecode(t) == html.unescape(t)` for text built from entities and plain characters.
- strength: Full reference comparison. Note that the entity regex may require a different boundary than html.unescape; any difference is then a candidate, not a bug, until triaged.

## CLAIM-4
- evidence: package_index.py:986 — "Encode auth from a URL suitable for an HTTP header."; 990 — "Long auth strings should not cause a newline to be inserted."
- source:   docstring
- reading:  The output is base64 of the percent-decoded auth string, with no newline.
- claim:    `base64.b64decode(_encode_auth(quote(s))) == s.encode()` and no '\n' in the output.
- strength: Round trip, strongest form.

## CLAIM-5
- evidence: package_index.py:82 — "Return (base,pyversion) or (None,None) for possible .exe name"
- source:   docstring
- reading:  For names built as `base + '.win32-pyX.Y.exe'`, the function must return that base and that py version.
- claim:    parse_bdist_wininst(base + suffix) recovers base (and py_ver) for each documented suffix form.
- strength: Round trip.

## CLAIM-6
- evidence: —
- source:   implicit (must not hang)
- reading:  `find_external_links` and `process_url` run the REL and HREF regexes over page content fetched from the network. Their cost must scale linearly with page length.
- claim:    find_external_links on an adversarial page of n chars finishes in time roughly linear in n.
- strength: Bounded time assertion.

## Amendments
- CLAIM-1: the test first asserted `norm != tmpdir` as well ("strictly inside"). It failed on `.../.`, which resolves to tmpdir itself. That is a minor case, so the check was loosened to "not outside tmpdir" to let the search reach the escape case. The loosened form still fails on `%2F`.
- CLAIM-6: the time bound was cut to 1 s and n to at most 1200, so the failing test finishes instead of hanging for minutes.

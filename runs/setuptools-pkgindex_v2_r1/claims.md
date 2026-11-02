# Claims for setuptools.package_index

## CLAIM-1
- evidence: setuptools/package_index.py:614-615 (`PackageIndex.download` docstring) — "If `spec` is a URL, it is downloaded to a subpath of `tmpdir`, and the local filename is returned."
  Also `_resolve_download_filename` docstring example: `str(pathlib.Path(du(url, root)).relative_to(root))` — the doctest itself relies on the result being relative to root.
- source:   docstring
- reading:  "a subpath of tmpdir" is a postcondition on the filename chosen for the download. The download filename is computed solely by `_resolve_download_filename(url, tmpdir)`, whose loop that strips `..` shows the author intends to keep the name inside tmpdir. "Subpath" rules out any path that, once normalised, lies outside tmpdir — absolute paths and `..` escapes alike. It leaves open what the name inside tmpdir is.
- claim:    For every http(s) URL, `os.path.realpath(_resolve_download_filename(url, tmpdir))` lies strictly inside `realpath(tmpdir)`.
- amended:  Changed "strictly inside" to "inside or equal to": the URL `.../d/.` resolves to tmpdir itself. That is harmless (the write just fails with IsADirectoryError) and is not an escape.
- strength: Strongest form: the resolved path is inside tmpdir. Did not weaken to "contains no '..'" (which the code already guarantees and which is strictly weaker — it passes on absolute paths).

## CLAIM-2
- evidence: package_index.py:1023-1032 `_encode_auth` docstring — ">>> str(_encode_auth('username%3Apassword')) 'dXNlcm5hbWU6cGFzc3dvcmQ='" and "Long auth strings should not cause a newline to be inserted."
- source:   docstring
- reading:  The function URL-unquotes then base64-encodes. The example fixes the semantics: output is base64 of the UTF-8 of the unquoted string. "should not cause a newline" holds for every input length.
- claim:    `base64.b64decode(_encode_auth(a)) == urllib.parse.unquote(a).encode()` and the result contains no '\n'.
- strength: Full round trip, stronger than "no newline".

## CLAIM-3
- evidence: package_index.py:986-988 — "# This pattern matches a character entity reference (a decimal numeric references, a hexadecimal numeric reference, or a named reference)."; `htmldecode` docstring "Decode HTML entities in the given text."
- source:   comment / reference
- reading:  Each matched entity is passed to `html.unescape`. "Decode HTML entities" names the same job `html.unescape` does, so the stdlib is a reference implementation.
- claim:    `htmldecode(t) == html.unescape(t)` for text built from entity-like fragments.
- strength: Full equality with a reference. If this fails on edge cases of semicolon-less entities, that is a divergence from a reference, not necessarily from a documented promise — will triage.

## CLAIM-4
- evidence: package_index.py:1101-1104 `_splituser` — "splituser('user[:passwd]@host[:port]') --> 'user[:passwd]', 'host[:port]'."
- source:   docstring
- reading:  Split on the last '@'; user part is None when there is no '@'.
- claim:    When `user` contains no '@' ... actually rpartition: for host strings without '@', returns (None, host); for `u + '@' + h` with h free of '@', returns (u, h).
- strength: Exact output.

## CLAIM-5
- evidence: package_index.py:82 `parse_bdist_wininst` — """Return (base,pyversion) or (None,None) for possible .exe name"""
- source:   docstring
- reading:  For names like `base.win32.exe`/`base.win32-pyX.Y.exe`, base + suffix must reconstruct the name; py version is the X.Y.
- claim:    For `name = base + '.win32-py' + v + '.exe'` (v = 'd.d'), the result's base == base and pyversion == v; for `base + '.win32.exe'`, base == base and pyversion None.
- strength: Exact output. (Return actually has 3 elements — noted, not tested as a bug: trivial doc drift.)

## CLAIM-6
- evidence: — (`REL` regex at package_index.py:214, applied by `find_external_links` to every fetched index page)
- source:   implicit
- reading:  Universal expectation: scanning a page of n bytes for links costs roughly O(n). The page is remote, untrusted HTML. The regex `<([^>]*\srel\s{0,10}=...` was itself introduced to fix a ReDoS (CVE-2022-40897), which confirms the author cares about this cost.
- claim:    `find_external_links(url, page)` runs in time roughly linear in `len(page)`; doubling the page should not ~quadruple the time.
- strength: Linear bound; asserted as a ratio between sizes n and 4n (must be < ~6x, quadratic gives ~16x).

## CLAIM-7
- evidence: package_index.py:917-926 `_vcs_split_rev_from_url` doctest — "vsrfu('git+https://github.com/pypa/setuptools@v69.0.0#egg-info=setuptools') -> ('https://github.com/pypa/setuptools', 'v69.0.0')"
- source:   docstring
- reading:  Strip the `vcs+` prefix, split `@rev` off the path end, drop the fragment.
- claim:    For `git+https://host/path@rev#frag` with path/rev free of '@', '#', '?', result == ('https://host/path', rev).
- strength: Exact output.

# Claims for setuptools.package_index

## CLAIM-1
- evidence: package_index.py:631-632 (PackageIndex.download docstring) — "If `spec` is a URL, it is downloaded to a subpath of `tmpdir`, and the local filename is returned."
- source:   docstring
- reading:  "a subpath of tmpdir" is a postcondition on the destination path. The path is
            computed by `_resolve_download_filename(url, tmpdir)` (called from `_download_url`),
            and the loop `while '..' in name` shows the author intends to neutralise path
            escape. "Subpath" rules out any destination outside tmpdir, whatever the URL.
- claim:    For every http(s) URL, `os.path.dirname(os.path.abspath(_resolve_download_filename(url, tmpdir))) == os.path.abspath(tmpdir)` — the file lands directly inside tmpdir.
- strength: Strongest form: the filename is a single component directly in tmpdir (the
            function joins exactly one name onto tmpdir). Weaker "is under tmpdir" also
            tested implicitly.

## CLAIM-2
- evidence: package_index.py:840-848 (_resolve_download_filename doctest) — url '.../setuptools-78.1.0.tar.gz' -> 'setuptools-78.1.0.tar.gz' relative to root
- source:   docstring (doctest)
- reading:  For an ordinary basename (no '..', no escapes) the file name is the URL basename unchanged.
- claim:    For safe basenames made of [A-Za-z0-9_.-] without '..', the result is os.path.join(tmpdir, basename).
- strength: exact equality, as the doctest shows.

## CLAIM-3
- evidence: package_index.py:1004-1008 — "Long auth strings should not cause a newline to be inserted."; `_encode_auth` docstring "Encode auth from a URL suitable for an HTTP header."
- source:   docstring
- reading:  Output is base64 of the percent-unquoted auth, with no newline. Round trip: b64decode(result) == unquote(auth).encode().
- claim:    '\n' not in _encode_auth(a) and base64.b64decode(_encode_auth(a)).decode() == unquote(a).
- strength: full round trip (stdlib reference) rather than only the no-newline check.

## CLAIM-4
- evidence: package_index.py:982-988 htmldecode — "Decode HTML entities in the given text."
- source:   docstring + reference (html.unescape)
- reading:  Decoding entities should agree with stdlib html.unescape on text containing entities.
- claim:    htmldecode(html.escape(s)) == s for any s.
- strength: round trip with stdlib encoder; a full equality with html.unescape(t) on arbitrary t is
            not claimed since entity_sub restricts which entities it matches.

## CLAIM-5
- evidence: package_index.py:84 parse_bdist_wininst — "Return (base,pyversion) or (None,None) for possible .exe name"
- source:   docstring + structure
- reading:  For name = base + '.win32-pyX.Y.exe' the returned base is `base` and pyversion 'X.Y'.
- claim:    parse_bdist_wininst(b + suffix) returns (b, ver, plat) for each of the four suffix forms.
- strength: exact.

## CLAIM-6
- evidence: package_index.py:888-897 _vcs_split_rev_from_url doctests
- source:   docstring
- reading:  'git+https://host/path@rev#frag' -> ('https://host/path', 'rev').
- claim:    for generated host/path/rev without '@', '#', the split returns the clean URL and rev.
- strength: exact.

## CLAIM-7
- evidence: —
- source:   implicit
- reading:  Regexes REL / HREF / entity_sub applied to an untrusted HTML page (find_external_links,
            process_index) must run in time roughly linear in the page size.
- claim:    find_external_links(url, page) and htmldecode(page) finish quickly on adversarial pages of ~20k chars.
- strength: timing bound.

## CLAIM-8
- evidence: package_index.py:177-182 interpret_distro_name — "find the pivot (p) that splits the name from the version. infer the version as the first item that has a digit."
- source:   comment
- reading:  name = parts before first digit-leading part; version = rest; joined with '-'.
- claim:    For basename = name + '-' + version where no name part begins with a digit and version starts with a digit, the yielded dist has project_name safe_name(name) and version safe_version(version).
- strength: exact under the comment's rule.

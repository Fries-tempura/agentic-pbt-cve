# Claims for setuptools.package_index

## CLAIM-1
- evidence: package_index.py:580-581 — "If `spec` is a URL, it is downloaded to a subpath of `tmpdir`, and the local filename is returned."
  plus package_index.py:822-824 — `while '..' in name: name = name.replace('..', '.').replace('\\', '_')` and doctest at :817 `str(pathlib.Path(du(url, root)).relative_to(root))`
- source:   docstring
- reading:  "a subpath of tmpdir" is a postcondition on the destination path. The `..` scrubbing in
            `_resolve_download_filename` shows the author intends the name never to leave tmpdir.
            The download path is exactly `_resolve_download_filename(url, tmpdir)` (see `_download_url`),
            so the claim transfers to that helper. It rules out any URL whose last path segment
            makes the joined path resolve outside tmpdir (absolute paths, traversal).
- claim:    For any http(s) URL, `os.path.realpath(_resolve_download_filename(url, tmpdir))` lies strictly inside `realpath(tmpdir)`.
- strength: Strongest form: strictly inside, for every URL. A weaker "no '..' in the name" reading would pass while absolute paths escape.

## CLAIM-2
- evidence: package_index.py:83 — """Return (base,pyversion) or (None,None) for possible .exe name"""
- source:   docstring + structure
- reading:  For a name built as `<base>.win32-py<X.Y>.exe` or `<base>.win-amd64-py<X.Y>.exe`, the parser must recover base and pyversion; for `<base>.win32.exe` base with no version. Non-.exe names give None base.
- claim:    parse_bdist_wininst(f"{b}{suffix}") recovers b and the version for each of the four suffix forms; non-.exe names give base None.
- strength: Full round trip on all forms.

## CLAIM-3
- evidence: package_index.py:566-575 — "Encode auth from a URL suitable for an HTTP header." / "Long auth strings should not cause a newline to be inserted."
- source:   docstring
- reading:  Result is base64 of the percent-unquoted string; decoding gives back unquote(auth); no newline.
- claim:    b64decode(_encode_auth(a)).decode() == unquote(a) and '\n' not in result.
- strength: round trip, strongest.

## CLAIM-4
- evidence: package_index.py:1037-1039 — "Decode HTML entities in the given text."
- source:   docstring / reference
- reading:  html.unescape is the stdlib reference for decoding HTML entities; decode_entity delegates to it per-match.
- claim:    htmldecode(t) == html.unescape(t) for text whose entities are well-formed (`&name;`, `&#N;`, `&#xH;`).
- strength: Restricted to well-formed entities, since the regex deliberately only matches some forms.

## CLAIM-5
- evidence: —
- source:   implicit
- reading:  find_external_links / process_url run REL and HREF regexes on untrusted HTML pages; cost must scale ~linearly with page size.
- claim:    find_external_links(url, page) runs in time roughly linear in len(page) (no quadratic blow-up for 50k char pages).
- strength: Asserted as a loose time bound.

## CLAIM-6
- evidence: package_index.py:906-917 — doctests `vsrfu('git+https://github.com/pypa/setuptools@v69.0.0#egg-info=setuptools')` -> `('https://github.com/pypa/setuptools', 'v69.0.0')`
- source:   docstring (doctest)
- reading:  "return a clean URL and resolved revision": the scheme prefix `vcs+` is stripped, `@rev` is split off the path, fragment dropped.
- claim:    For url = f"git+https://{host}/{path}@{rev}#egg=x", result == (f"https://{host}/{path}", rev).
- strength: Exact equality.

## CLAIM-7
- evidence: package_index.py:166-176 — "Generate the interpretation of a source distro name ... infer the version as the first item that has a digit."
- source:   comment
- reading:  For basename `name-version` where name segments have no leading digits and version starts with a digit, project_name derived from name and version equals the version text.
- claim:    interpret_distro_name(loc, f"{name}-{ver}", None) yields one Distribution with project_name == safe_name(name) and version == safe_version(ver)-equivalent.
- strength: exact.

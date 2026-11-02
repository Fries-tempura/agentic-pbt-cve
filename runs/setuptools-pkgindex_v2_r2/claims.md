# Claims for setuptools.package_index (setuptools 78.1.0)

## CLAIM-1
- evidence: package_index.py:582-583 (PackageIndex.download docstring) — "If `spec` is a URL, it is downloaded to a subpath
  of `tmpdir`, and the local filename is returned."
- source:   docstring
- reading:  `download` -> `_download_url` -> `_resolve_download_filename(url, tmpdir)` picks the
            destination path. "a subpath of `tmpdir`" is a postcondition on that path: after
            normalisation it must lie inside `tmpdir`. It rules out absolute paths and `..`
            escapes for *any* URL, since the docstring places no restriction on the URL. The
            `while '..' in name` loop in `_resolve_download_filename` is the author's own attempt
            to enforce this, which confirms the intent.
- claim:    For every http(s) URL, `os.path.realpath(_resolve_download_filename(url, tmpdir))`
            is strictly inside `os.path.realpath(tmpdir)`.
- strength: Strongest form. A weaker reading ("the result starts with tmpdir as a string")
            would pass on `tmpdir + '/../x'`; I check the normalised path instead.
- amended:  Relaxed "strictly inside" to "not outside" (equal to tmpdir allowed): URL path '.'
            maps to tmpdir itself, which is a failed download rather than an escape, and is
            not what the docstring guards against.

## CLAIM-2
- evidence: package_index.py:953-957 (_encode_auth doctest) — "Encode auth from a URL suitable for an HTTP header.
  >>> str(_encode_auth('username%3Apassword'))  'dXNlcm5hbWU6cGFzc3dvcmQ='" and
  "Long auth strings should not cause a newline to be inserted."
- source:   docstring
- reading:  The value is URL-unquoted, then base64 encoded. Round trip: base64-decoding the
            result gives back `unquote(auth)` encoded as UTF-8, and the result has no newline.
- claim:    `b64decode(_encode_auth(a)).decode() == unquote(a)` and `'\n' not in _encode_auth(a)`.
- strength: Full round trip, strongest available.

## CLAIM-3
- evidence: package_index.py:861-876 (_vcs_split_rev_from_url docstring) — "Given a possible VCS URL, return a clean URL and resolved revision if any."
  with doctest `('https://github.com/pypa/setuptools', 'v69.0.0')`
- source:   docstring
- reading:  For `vcs+scheme://host/path@rev#frag`, the clean URL is `scheme://host/path` (no
            `vcs+` prefix, no fragment, no `@rev`) and the revision is `rev`.
- claim:    For generated host/path/rev without '@' or '#', the function returns
            `(f"{scheme}://{host}{path}", rev)`.
- strength: Exact equality, strongest form.

## CLAIM-4
- evidence: package_index.py:916-923 (htmldecode docstring) — "Decode HTML entities in the given text."
- source:   docstring / reference
- reading:  `html.unescape` is the reference for decoding HTML entities; on text whose entities
            are all terminated with ';' the two must agree.
- claim:    `htmldecode(s) == html.unescape(s)` for text built from literal chars and
            well-formed `&name;`, `&#NN;`, `&#xHH;` references.
- strength: Restricted to well-formed references; behaviour on unterminated ones is not
            documented.

## CLAIM-5
- evidence: —
- source:   implicit (cost scales with input)
- reading:  `find_external_links(url, page)` runs the `REL` regex over a downloaded HTML page,
            which is attacker-controlled content from an index/find-links server. Every correct
            implementation must scan a page in roughly linear time.
- claim:    `find_external_links` on a page of n characters finishes in time ~linear in n
            (doubling n roughly doubles, not quadruples, the time).
- strength: Implicit universal expectation; no stronger form.

## CLAIM-6
- evidence: package_index.py:200-203 (interpret_distro_name) — "find the pivot (p) that splits the name from the version.
  infer the version as the first item that has a digit."
- source:   comment
- reading:  For basename `name-version` where no dash-separated part of `name` starts with a
            digit and `version` starts with a digit, the yielded Distribution has
            project_name == safe_name(name) and version == safe_version(version)-ish.
- claim:    The generated Distribution's project_name is `safe_name(name)` for such inputs.
- strength: Checked project_name only; version normalisation goes through pkg_resources.

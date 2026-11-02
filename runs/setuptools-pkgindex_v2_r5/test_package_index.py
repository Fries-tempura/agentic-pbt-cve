import base64
import html
import os
import re
import time
import urllib.parse

from hypothesis import given, settings, strategies as st

from setuptools.package_index import (
    PackageIndex,
    _encode_auth,
    find_external_links,
    htmldecode,
    parse_bdist_wininst,
)

TMPDIR = "/tmp/pi_tmp"

seg_atoms = st.sampled_from(
    ["a", "b", "pkg", "1.0", ".", "..", "%2F", "%2f", "%5C", "\\", "%2E", "-", "_", ".tar.gz", "/"]
)
segment = st.lists(seg_atoms, min_size=1, max_size=8).map("".join)


@settings(max_examples=1000)
@given(segment)
def test_download_filename_inside_tmpdir(seg):
    """CLAIM-1: the download filename is strictly inside tmpdir."""
    url = "https://files.example.org/packages/" + seg
    result = PackageIndex._resolve_download_filename(url, TMPDIR)
    norm = os.path.normpath(result)
    assert os.path.commonpath([norm, TMPDIR]) == TMPDIR, (url, result)


hostname = st.from_regex(r"[a-z]{1,8}\.(com|org)", fullmatch=True)
pathpart = st.lists(st.from_regex(r"[A-Za-z0-9_.-]{1,6}", fullmatch=True), max_size=4).map(
    lambda xs: "/" + "/".join(xs)
)
rev = st.from_regex(r"[A-Za-z0-9_.-]{1,8}", fullmatch=True)


@given(st.sampled_from(["http", "https"]), hostname, pathpart, st.none() | rev)
def test_vcs_split_rev(scheme, host, path, r):
    """CLAIM-2: clean URL and revision are recovered."""
    clean = f"{scheme}://{host}{path}"
    if r is None:
        assert PackageIndex._vcs_split_rev_from_url(clean) == (clean, None)
    else:
        url = f"git+{clean}@{r}"
        assert PackageIndex._vcs_split_rev_from_url(url) == (clean, r)


entity = st.sampled_from(
    ["&amp;", "&lt;", "&gt;", "&quot;", "&#39;", "&#x41;", "&#65;", "&amp", "&lt", "&copy;", "&nbsp;"]
)
plain = st.text(alphabet="ab;&#x1 ", max_size=3)
html_text = st.lists(st.one_of(entity, plain), max_size=8).map("".join)


@settings(max_examples=1000)
@given(html_text)
def test_htmldecode_matches_stdlib(t):
    """CLAIM-3: htmldecode agrees with html.unescape."""
    assert htmldecode(t) == html.unescape(t)


@given(st.text())
def test_encode_auth_round_trip(s):
    """CLAIM-4: base64 of the unquoted auth, no newline."""
    enc = _encode_auth(urllib.parse.quote(s, safe=""))
    assert "\n" not in enc
    assert base64.b64decode(enc) == s.encode()


@given(
    st.from_regex(r"[A-Za-z0-9_.-]{1,10}", fullmatch=True),
    st.sampled_from(["2.7", "3.9", "3.1"]),
    st.sampled_from(["win32", "win-amd64"]),
    st.booleans(),
)
def test_parse_bdist_wininst(base, pyver, plat, with_py):
    """CLAIM-5: base / py version / platform recovered from .exe name."""
    name = f"{base}.{plat}" + (f"-py{pyver}" if with_py else "") + ".exe"
    assert parse_bdist_wininst(name) == (base, pyver if with_py else None, plat)


@settings(max_examples=20, deadline=None)
@given(st.sampled_from(["< rel=", "<a rel=" + " " * 10, "<x rel", "<" + " rel" * 5]), st.integers(200, 1200))
def test_find_external_links_linear(chunk, n):
    """CLAIM-6: regex scanning of a page is roughly linear."""
    page = chunk * n
    t0 = time.perf_counter()
    list(find_external_links("https://x.org/", page))
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, (chunk, n, elapsed)

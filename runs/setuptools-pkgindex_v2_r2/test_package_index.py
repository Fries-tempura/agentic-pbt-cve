import base64
import html
import os
import time
import urllib.parse

from hypothesis import given, settings, strategies as st
from pkg_resources import safe_name

from setuptools.package_index import (
    PackageIndex,
    _encode_auth,
    find_external_links,
    htmldecode,
    interpret_distro_name,
)

TMPDIR = "/tmp/pkgindex_dl"

# Characters the resolver treats specially: '/', '\\', '.', plus percent-encoded forms.
segment = st.lists(
    st.sampled_from(["a", "b", ".", "..", "%2F", "%2f", "%5C", "/", "\\", "-", "x.tar.gz"]),
    min_size=1,
    max_size=6,
).map("".join)


@settings(max_examples=1000)
@given(prefix=st.lists(st.sampled_from(["p", "q"]), max_size=3), last=segment)
def test_download_target_inside_tmpdir(prefix, last):
    """CLAIM-1: download destination is a subpath of tmpdir."""
    url = "https://example.com/" + "/".join(prefix + [last])
    dest = PackageIndex._resolve_download_filename(url, TMPDIR)
    root = os.path.realpath(TMPDIR)
    real = os.path.realpath(dest)
    assert os.path.commonpath([root, real]) == root, (url, dest)


@given(st.text())
def test_encode_auth_round_trip(a):
    """CLAIM-2: base64 round trip of the unquoted auth, no newlines."""
    enc = _encode_auth(a)
    assert "\n" not in enc
    assert base64.b64decode(enc).decode() == urllib.parse.unquote(a)


ident = st.text(alphabet="abcxyz0123456789_.", min_size=1, max_size=8)


@given(
    scheme=st.sampled_from(["http", "https", "ssh"]),
    vcs=st.sampled_from(["git", "hg"]),
    host=ident,
    path=st.lists(ident, min_size=1, max_size=4).map(lambda p: "/" + "/".join(p)),
    rev=st.none() | ident,
    frag=st.none() | ident,
)
def test_vcs_split(scheme, vcs, host, path, rev, frag):
    """CLAIM-3: vcs URL splits into clean URL and revision."""
    url = f"{vcs}+{scheme}://{host}{path}"
    if rev is not None:
        url += "@" + rev
    if frag is not None:
        url += "#egg=" + frag
    assert PackageIndex._vcs_split_rev_from_url(url) == (f"{scheme}://{host}{path}", rev)


entity = st.one_of(
    st.sampled_from(["&amp;", "&lt;", "&gt;", "&quot;", "&nbsp;", "&eacute;", "&copy;"]),
    st.integers(32, 0x10FFFF).filter(lambda c: not 0xD800 <= c <= 0xDFFF).map(lambda c: f"&#{c};"),
    st.integers(32, 0x10FFFF).filter(lambda c: not 0xD800 <= c <= 0xDFFF).map(lambda c: f"&#x{c:x};"),
)
plain = st.text(alphabet="abc /?=.:-#;", max_size=4)


@given(st.lists(st.one_of(entity, plain), max_size=8).map("".join))
def test_htmldecode_matches_unescape(s):
    """CLAIM-4: htmldecode agrees with html.unescape on well-formed references."""
    assert htmldecode(s) == html.unescape(s)


def _time(page):
    t = time.perf_counter()
    list(find_external_links("http://a/", page))
    return time.perf_counter() - t


@settings(max_examples=5, deadline=None)
@given(st.sampled_from(["<", "< ", "<a "]))
def test_find_external_links_linear(unit):
    """CLAIM-5: scanning a page costs ~linear time in its length."""
    n = 4000
    small = _time(unit * n)
    big = _time(unit * (4 * n))
    # linear => ~4x; quadratic => ~16x
    assert big < max(10 * small, 0.05), (unit, small, big)


name_part = st.text(alphabet="abcxyz_", min_size=1, max_size=6)


@given(
    name=st.lists(name_part, min_size=1, max_size=3).map("-".join),
    version=st.from_regex(r"\A[0-9]{1,3}(\.[0-9]{1,3}){0,2}\Z"),
)
def test_interpret_distro_name(name, version):
    """CLAIM-6: name/version pivot at the first part starting with a digit."""
    dists = list(interpret_distro_name("/x", f"{name}-{version}", None))
    assert len(dists) == 1
    assert dists[0].project_name == safe_name(name)

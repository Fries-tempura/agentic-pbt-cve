import base64, html, os, time, urllib.parse
from hypothesis import given, settings, strategies as st, HealthCheck
from setuptools.package_index import (PackageIndex, _encode_auth, htmldecode,
    _splituser, parse_bdist_wininst, find_external_links)

TMP = os.path.realpath("/tmp/pi_dl_root")
seg_chars = "abc.-_/\\%2Ff"
segment = st.text(alphabet="abc.-_/\\", min_size=1, max_size=12)

@settings(max_examples=1000)
@given(st.lists(segment, min_size=1, max_size=4), st.booleans())
def test_download_stays_in_tmpdir(segs, quote_all):
    """CLAIM-1: the resolved download filename lies inside tmpdir."""
    last = urllib.parse.quote(segs[-1], safe="" if quote_all else "/")
    url = "https://example.com/" + "/".join(["d"] + segs[:-1]) .replace("//", "/") + "/" + last
    p = os.path.realpath(PackageIndex._resolve_download_filename(url, TMP))
    assert os.path.commonpath([p, TMP]) == TMP, (url, p)

@given(st.text())
def test_encode_auth_roundtrip(a):
    """CLAIM-2: base64 round trip of unquoted auth, no newline."""
    e = _encode_auth(a)
    assert "\n" not in e
    assert base64.b64decode(e) == urllib.parse.unquote(a).encode()

ent = st.sampled_from(["&amp;", "&lt;", "&#65;", "&#x41;", "&amp", "&gt", "&", ";", "a", "#", "x", "1",
                       "&nbsp;", "&copy", "&notit;", "&#0;", "&#x110000;", ".", ":"])
@settings(max_examples=1000)
@given(st.lists(ent, max_size=8).map("".join))
def test_htmldecode_matches_unescape(t):
    """CLAIM-3: htmldecode agrees with html.unescape."""
    assert htmldecode(t) == html.unescape(t)

@given(st.text(alphabet="ab:@1", max_size=8), st.text(alphabet="ab:.1", max_size=8))
def test_splituser(u, h):
    """CLAIM-4: split on '@'."""
    assert _splituser(h) == (None, h)
    assert _splituser(u + "@" + h) == (u, h)

@given(st.text(alphabet="abcXY-_.0123", min_size=1, max_size=10),
       st.from_regex(r"\A[0-9]\.[0-9]\Z"), st.sampled_from(["win32", "win-amd64"]))
def test_bdist_wininst(base, v, plat):
    """CLAIM-5: base and pyversion reconstruct the name."""
    assert parse_bdist_wininst(f"{base}.{plat}-py{v}.exe")[:2] == (base, v)
    assert parse_bdist_wininst(f"{base}.{plat}.exe")[:2] == (base, None)

@settings(max_examples=10, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.sampled_from(["< ", "<\t", "< a", "<a ", "< rel "]))
def test_find_external_links_linear(unit):
    """CLAIM-6: link scanning time is roughly linear in page size."""
    def t(n):
        page = unit * n
        s = time.perf_counter(); list(find_external_links("http://x/", page)); return time.perf_counter() - s
    small, big = t(1500), t(6000)
    assert big < max(small, 1e-3) * 6, (unit, small, big)

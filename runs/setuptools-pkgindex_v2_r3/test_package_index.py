import base64, html, os, string, time, tempfile, urllib.parse
from hypothesis import given, settings, assume, strategies as st
from setuptools.package_index import (
    PackageIndex, parse_bdist_wininst, _encode_auth, htmldecode,
    find_external_links, interpret_distro_name,
)

seg_chars = string.ascii_letters + string.digits + "._-/\\%:" 
TMP = os.path.realpath(tempfile.mkdtemp())


@settings(max_examples=1000)
@given(seg=st.text(alphabet=seg_chars, min_size=1, max_size=20))
def test_download_stays_in_tmpdir(seg):
    """CLAIM-1: URL downloads resolve to a path strictly inside tmpdir."""
    url = "https://example.com/pkgs/" + urllib.parse.quote(seg, safe="")
    path = os.path.realpath(PackageIndex._resolve_download_filename(url, TMP))
    assert os.path.commonpath([path, TMP]) == TMP and path != TMP, (url, path)


base_st = st.text(alphabet=string.ascii_letters + string.digits + "-_.", min_size=1, max_size=15)
ver_st = st.from_regex(r"\A[0-9]\.[0-9]\Z")


@given(base=base_st, ver=ver_st)
def test_wininst_roundtrip(base, ver):
    """CLAIM-2: parse_bdist_wininst recovers base and python version."""
    assert parse_bdist_wininst(f"{base}.win32-py{ver}.exe")[:2] == (base, ver)
    assert parse_bdist_wininst(f"{base}.win-amd64-py{ver}.exe")[:2] == (base, ver)
    assert parse_bdist_wininst(f"{base}.win32.exe")[:2] == (base, None)
    assert parse_bdist_wininst(f"{base}.win-amd64.exe")[:2] == (base, None)
    assert parse_bdist_wininst(f"{base}.tar.gz")[0] is None


@given(st.text())
def test_encode_auth_roundtrip(s):
    """CLAIM-3: _encode_auth is base64 of the unquoted auth, without newlines."""
    a = urllib.parse.quote(s)
    enc = _encode_auth(a)
    assert "\n" not in enc
    assert base64.b64decode(enc).decode() == s


entity = st.one_of(
    st.sampled_from(["&amp;", "&lt;", "&gt;", "&quot;", "&nbsp;", "&eacute;"]),
    st.integers(32, 0x10FFFF).filter(lambda c: not 0xD800 <= c <= 0xDFFF).map(lambda c: f"&#{c};"),
    st.integers(32, 0x10FFFF).filter(lambda c: not 0xD800 <= c <= 0xDFFF).map(lambda c: f"&#x{c:x};"),
)
plain = st.text(alphabet="abc <>/=\"' ", max_size=5)


@settings(max_examples=500)
@given(st.lists(st.one_of(entity, plain), max_size=10))
def test_htmldecode_matches_stdlib(parts):
    """CLAIM-4: htmldecode equals html.unescape on well-formed entities."""
    t = "".join(parts)
    assert htmldecode(t) == html.unescape(t)


@settings(max_examples=10, deadline=None)
@given(unit=st.sampled_from(["< ", "<a ", "<a rel ", "<\t", "<a href=x "]))
def test_find_external_links_linear(unit):
    """CLAIM-5: find_external_links cost scales roughly linearly with page size."""
    def t(n):
        page = unit * n
        s = time.perf_counter()
        list(find_external_links("http://x/", page))
        return time.perf_counter() - s
    small, big = t(2000), t(16000)
    assert big < max(small, 0.005) * 8 * 4, (unit, small, big)


host_st = st.from_regex(r"\A[a-z][a-z0-9]{0,8}\.(com|org)\Z")
path_st = st.from_regex(r"\A[a-z0-9_]{1,8}(/[a-z0-9_]{1,8}){0,3}\Z")
rev_st = st.from_regex(r"\A[A-Za-z0-9._]{1,10}\Z")


@given(host=host_st, path=path_st, rev=rev_st)
def test_vcs_split(host, path, rev):
    """CLAIM-6: vcs URL splits into clean URL and revision."""
    url = f"git+https://{host}/{path}@{rev}#egg=x"
    assert PackageIndex._vcs_split_rev_from_url(url) == (f"https://{host}/{path}", rev)


name_seg = st.from_regex(r"\A[A-Za-z][A-Za-z0-9_]{0,6}\Z")
ver = st.from_regex(r"\A[0-9]{1,3}(\.[0-9]{1,3}){0,3}\Z")


@given(names=st.lists(name_seg, min_size=1, max_size=3), v=ver)
def test_interpret_distro_name(names, v):
    """CLAIM-7: name/version split on the first digit-led segment."""
    from pkg_resources import safe_name, safe_version
    ds = list(interpret_distro_name("/x", "-".join(names) + "-" + v, None))
    assert len(ds) == 1
    assert ds[0].project_name == safe_name("-".join(names))
    assert ds[0].version == safe_version(v)

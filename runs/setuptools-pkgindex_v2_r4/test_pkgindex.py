import base64, html, os, time, urllib.parse
import pytest
from hypothesis import given, settings, strategies as st, assume
from setuptools.package_index import (
    PackageIndex, _encode_auth, htmldecode, parse_bdist_wininst,
    find_external_links, interpret_distro_name,
)
from pkg_resources import safe_name, safe_version

TMP = "/tmp/pkgidx_dl"
resolve = PackageIndex._resolve_download_filename

seg_tokens = st.sampled_from(["a", "b", ".", "..", "%2F", "%2f", "%5C", "\\", "%2E", "x.tar.gz", "-1.0"])
segment = st.lists(seg_tokens, min_size=1, max_size=8).map("".join)

@settings(max_examples=2000)
@given(dirs=st.lists(st.sampled_from(["pkgs", "a", "b"]), max_size=3), last=segment)
def test_download_stays_in_tmpdir(dirs, last):
    """CLAIM-1: download target is directly inside tmpdir."""
    url = "https://example.com/" + "/".join(dirs + [last])
    path = os.path.abspath(resolve(url, TMP))
    assume(path != os.path.abspath(TMP))  # bare "." names the dir itself; not an escape
    assert os.path.dirname(path) == os.path.abspath(TMP), (url, path)

@given(st.from_regex(r"[A-Za-z0-9_][A-Za-z0-9_\-]{0,10}(\.[A-Za-z0-9_\-]{1,5}){0,3}", fullmatch=True))
def test_safe_name_unchanged(name):
    """CLAIM-2: ordinary basenames are kept verbatim."""
    assume(".." not in name and not name.endswith(".egg.zip"))
    assert resolve("https://h/p/" + name, TMP) == os.path.join(TMP, name)

@given(st.text())
def test_encode_auth_roundtrip(s):
    """CLAIM-3: base64 of unquoted auth, no newline."""
    a = urllib.parse.quote(s)
    out = _encode_auth(a)
    assert "\n" not in out
    assert base64.b64decode(out).decode() == s

@given(st.text(alphabet=st.characters(codec="utf-8", exclude_categories=["Cs"])))
def test_htmldecode_roundtrip(s):
    """CLAIM-4: htmldecode inverts html.escape."""
    assert htmldecode(html.escape(s)) == s

@given(base=st.from_regex(r"[A-Za-z][A-Za-z0-9_.\-]{0,15}", fullmatch=True),
       ver=st.from_regex(r"[23]\.[0-9]", fullmatch=True))
def test_parse_bdist_wininst(base, ver):
    """CLAIM-5: base / pyversion / platform extraction for all four forms."""
    assert parse_bdist_wininst(base + ".win32.exe") == (base, None, "win32")
    assert parse_bdist_wininst(base + f".win32-py{ver}.exe") == (base, ver, "win32")
    assert parse_bdist_wininst(base + ".win-amd64.exe") == (base, None, "win-amd64")
    assert parse_bdist_wininst(base + f".win-amd64-py{ver}.exe") == (base, ver, "win-amd64")

ident = st.from_regex(r"[a-z0-9]{1,8}", fullmatch=True)
@given(host=ident, path=st.lists(ident, min_size=1, max_size=3), rev=st.one_of(st.none(), ident))
def test_vcs_split(host, path, rev):
    """CLAIM-6: VCS URL split into clean URL and rev."""
    clean = f"https://{host}.com/" + "/".join(path)
    url = "git+" + clean + (f"@{rev}" if rev else "") + "#egg=x"
    assert PackageIndex._vcs_split_rev_from_url(url) == (clean, rev)

@pytest.mark.parametrize("page", [
    "<a" + " " * 20000,
    "<a rel" + " " * 20000,
    "<" + "a rel=x " * 3000,
    "href=" * 5000,
    "&" + "a" * 20000,
    "<" * 20000,
    "< rel=" * 3000,
])
def test_no_regex_blowup(page):
    """CLAIM-7: link scanning is roughly linear on adversarial pages."""
    t = time.perf_counter()
    list(find_external_links("https://h/", page))
    htmldecode(page)
    assert time.perf_counter() - t < 2.0

namepart = st.from_regex(r"[A-Za-z][A-Za-z0-9_.]{0,6}", fullmatch=True)
verpart = st.from_regex(r"[0-9][A-Za-z0-9.]{0,6}", fullmatch=True)
@given(name=st.lists(namepart, min_size=1, max_size=3), ver=st.lists(verpart, min_size=1, max_size=2))
def test_interpret_distro_name(name, ver):
    """CLAIM-8: name/version split at first digit-leading part."""
    assume(not any(p.startswith("py") for p in ver))
    n, v = "-".join(name), "-".join(ver)
    ds = list(interpret_distro_name("loc", n + "-" + v, None))
    assert len(ds) == 1
    assert ds[0].project_name == safe_name(n)
    assert ds[0].version == safe_version(v)

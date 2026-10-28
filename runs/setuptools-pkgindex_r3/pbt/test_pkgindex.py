import base64, os, urllib.parse
from hypothesis import given, settings, strategies as st, assume
from setuptools.package_index import (
    PackageIndex, egg_info_for_url, _encode_auth, Credential, parse_bdist_wininst,
)

seg = st.text(st.characters(codec="utf-8", exclude_characters="\x00"), min_size=1)

@settings(max_examples=1000)
@given(seg)
def test_download_filename_stays_in_tmpdir(name):
    # download(): "If spec is a URL, it is downloaded to a subpath of tmpdir"
    tmpdir = "/tmp/pkgidx_dl"
    url = "https://example.com/packages/" + urllib.parse.quote(name, safe="")
    result = PackageIndex._resolve_download_filename(url, tmpdir)
    real = os.path.realpath(result)
    assert os.path.commonpath([real, os.path.realpath(tmpdir)]) == os.path.realpath(tmpdir), (url, result)

@given(st.text(st.characters(codec="utf-8"), min_size=0), st.text(st.characters(codec="utf-8")))
def test_encode_auth_roundtrip(user, pw):
    assume(":" not in user)
    raw = f"{user}:{pw}"
    enc = _encode_auth(urllib.parse.quote(raw, safe=""))
    assert base64.b64decode(enc).decode() == raw
    assert "\n" not in enc

@given(st.text(min_size=1).filter(lambda s: '@' not in s and '#' not in s and '/' not in s and '?' not in s), st.text(alphabet="abcdef0123456789v.", min_size=1))
def test_vcs_split_rev(path, rev):
    url = f"git+https://github.com/org/{urllib.parse.quote(path)}@{rev}"
    clean, r = PackageIndex._vcs_split_rev_from_url(url)
    assert r == rev
    assert clean == f"https://github.com/org/{urllib.parse.quote(path)}"

@given(st.from_regex(r"[A-Za-z][A-Za-z0-9_.]{0,10}-[0-9][0-9.]{0,5}", fullmatch=True),
       st.sampled_from([".win32.exe", ".win32-py3.8.exe", ".win-amd64.exe", ".win-amd64-py3.9.exe"]))
def test_parse_bdist_wininst(base, suffix):
    b, pyv, plat = parse_bdist_wininst(base + suffix)
    assert b == base
    assert plat == ("win32" if "win32" in suffix else "win-amd64")

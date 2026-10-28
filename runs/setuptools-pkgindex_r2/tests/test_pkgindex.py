import os, base64, urllib.parse
from hypothesis import given, settings, strategies as st
from setuptools.package_index import PackageIndex, _encode_auth, egg_info_for_url, parse_bdist_wininst

seg = st.text(alphabet=st.characters(codec="ascii", exclude_characters="\x00"), min_size=1)

@settings(max_examples=1000)
@given(seg)
def test_download_filename_stays_in_tmpdir(name):
    tmpdir = "/tmp/pkgidx_root"
    url = "https://example.com/packages/" + urllib.parse.quote(name, safe="")
    result = PackageIndex._resolve_download_filename(url, tmpdir)
    real = os.path.normpath(result)
    assert os.path.commonpath([real, tmpdir]) == tmpdir, (url, result)

@given(st.text())
def test_encode_auth_roundtrip(s):
    q = urllib.parse.quote(s)
    assert base64.b64decode(_encode_auth(q)).decode() == s

@given(st.text(alphabet="abcdefgh-_.0123456789", min_size=1))
def test_wininst(base):
    for suffix, plat in [(".win32.exe", "win32"), (".win-amd64.exe", "win-amd64")]:
        assert parse_bdist_wininst(base + suffix) == (base, None, plat)
    for suffix, plat in [(".win32-py2.7.exe", "win32"), (".win-amd64-py3.9.exe", "win-amd64")]:
        b, v, p = parse_bdist_wininst(base + suffix)
        assert (b, p) == (base, plat) and v == suffix[-7:-4]

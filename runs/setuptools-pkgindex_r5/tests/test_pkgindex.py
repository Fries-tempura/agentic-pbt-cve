import os, base64, urllib.parse
from hypothesis import given, settings, strategies as st
from setuptools.package_index import PackageIndex, _encode_auth, egg_info_for_url

seg = st.text(alphabet=st.characters(codec="utf-8", exclude_categories=["Cs"], exclude_characters="\x00"), min_size=1)

@settings(max_examples=1000)
@given(seg)
def test_download_filename_is_subpath_of_tmpdir(name):
    tmpdir = "/tmp/pkgidx_root"
    url = "https://example.com/packages/" + urllib.parse.quote(name, safe="")
    result = PackageIndex._resolve_download_filename(url, tmpdir)
    real = os.path.normpath(result)
    assert os.path.commonpath([real, tmpdir]) == tmpdir, (url, result)

@given(st.text(alphabet=st.characters(exclude_categories=["Cs"])))
def test_encode_auth_roundtrip(auth):
    quoted = urllib.parse.quote(auth, safe="")
    enc = _encode_auth(quoted)
    assert base64.b64decode(enc).decode() == auth
    assert "\n" not in enc

@given(seg.filter(lambda s: "#" not in s))
def test_egg_info_for_url_basename(name):
    url = "https://example.com/x/" + urllib.parse.quote(name, safe="")
    base, frag = egg_info_for_url(url)
    assert base == name and frag == ""

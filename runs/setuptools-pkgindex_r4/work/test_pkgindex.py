import os, urllib.parse, tempfile
from hypothesis import given, settings, strategies as st
from setuptools.package_index import PackageIndex, egg_info_for_url, htmldecode, _encode_auth
import base64

seg = st.text(st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"), min_size=1)

@settings(max_examples=2000)
@given(seg)
def test_download_filename_stays_in_tmpdir(name):
    tmpdir = tempfile.gettempdir() + "/pkgroot"
    url = "https://example.com/packages/" + urllib.parse.quote(name, safe="")
    result = PackageIndex._resolve_download_filename(url, tmpdir)
    root = os.path.realpath(tmpdir)
    assert os.path.commonpath([root, os.path.realpath(result)]) == root, (url, result)

@given(st.text())
def test_encode_auth_roundtrip(s):
    enc = _encode_auth(urllib.parse.quote(s))
    assert base64.b64decode(enc).decode() == s
    assert "\n" not in enc

@given(st.text(st.characters(blacklist_characters="&")))
def test_htmldecode_identity_without_entities(s):
    assert htmldecode(s) == s

@given(st.from_regex(r"[A-Za-z0-9._-]{1,20}", fullmatch=True))
def test_vcs_split_rev(rev):
    url = f"git+https://github.com/a/b@{rev}#egg=b"
    assert PackageIndex._vcs_split_rev_from_url(url) == ("https://github.com/a/b", rev)

import os, urllib.parse
from hypothesis import given, settings, strategies as st
from setuptools.package_index import PackageIndex, egg_info_for_url

seg = st.text(st.characters(min_codepoint=0x21, max_codepoint=0x7e), min_size=1, max_size=20)

@settings(max_examples=2000)
@given(st.lists(seg, min_size=1, max_size=4))
def test_download_filename_stays_in_tmpdir(parts):
    tmpdir = "/tmp/pkgidx_root"
    path = "/".join(urllib.parse.quote(p, safe="") for p in parts)
    url = f"https://files.example.org/packages/{path}"
    result = PackageIndex._resolve_download_filename(url, tmpdir)
    assert os.path.dirname(os.path.abspath(result)) == tmpdir, (url, result)

@given(st.lists(seg, min_size=1, max_size=4))
def test_egg_info_basename(parts):
    path = "/".join(urllib.parse.quote(p, safe="") for p in parts)
    base, frag = egg_info_for_url(f"https://example.org/{path}")
    assert base == parts[-1].split('#', 1)[0]

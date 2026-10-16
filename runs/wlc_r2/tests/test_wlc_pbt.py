import os
import tempfile
from argparse import Namespace
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from unittest import mock

from hypothesis import given, settings, strategies as st, HealthCheck

import wlc
from wlc.config import WeblateConfig
from wlc.main import Download, Command

slug_chars = st.lists(
    st.sampled_from(["..", ".", "/", "a", "b-c", "_", "x"]), min_size=1, max_size=8
).map("".join)


class FakeComponent:
    def __init__(self, pslug, cslug):
        self.project = Namespace(slug=pslug)
        self.slug = cslug

    def download(self, convert):
        return b"zipdata"


# P1: download_component stores files inside --output directory
@settings(max_examples=300, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(slug_chars, slug_chars)
def test_download_component_stays_in_output_dir(pslug, cslug):
    with tempfile.TemporaryDirectory() as root:
        out = os.path.join(root, "a", "b", "out")
        args = Namespace(convert=None, output=out, no_glossary=False, format="text")
        cmd = Download(args, WeblateConfig(), stdout=StringIO())
        written = []
        real_open = open

        def fake_open(path, mode="r", *a, **k):
            written.append(Path(path))
            return real_open(os.devnull, mode)

        with mock.patch("builtins.open", fake_open), \
             mock.patch.object(Path, "mkdir", lambda *a, **k: None):
            try:
                cmd.download_component(FakeComponent(pslug, cslug))
            except OSError:
                return
        target = os.path.realpath(os.path.join(root, "a", "b", "out", written[0]))
        assert os.path.commonpath([target, os.path.realpath(out)]) == os.path.realpath(out), (pslug, cslug, written[0])


# P2: SSL verification is only disabled for localhost
hostnames = st.from_regex(r"\A[a-z][a-z0-9-]{0,10}(\.[a-z][a-z0-9-]{0,10}){0,3}\Z")


@given(st.one_of(hostnames, hostnames.map(lambda h: "127.0.0.1." + h),
                 hostnames.map(lambda h: "127.0.0.10" + "." + h)),
       st.sampled_from(["", ":8443"]))
def test_ssl_verify_for_non_localhost(host, port):
    url = f"https://{host}{port}/api/"
    import urllib.parse
    hostname = urllib.parse.urlparse(url).hostname
    if hostname == "127.0.0.1":
        return
    assert wlc.Weblate._should_verify_ssl(url), url


# P3: HTML output escapes values
class Collect(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)


@given(st.builds(lambda a, t, b: a + "<" + t + ">" + b, st.text(), st.from_regex(r"\A[a-z]{1,6}\Z"), st.text()))
def test_html_output_well_formed(value):
    out = StringIO()
    cmd = Command.__new__(Command)
    cmd.stdout = out
    cmd.args = Namespace(format="html")
    cmd.print({"name": value})
    p = Collect()
    p.feed(out.getvalue())
    assert set(p.tags) <= {"table", "tr", "th", "td"}, (value, p.tags)

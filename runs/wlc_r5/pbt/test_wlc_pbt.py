import os
import tempfile
from argparse import Namespace
from pathlib import Path
from unittest import mock

from hypothesis import given, settings, strategies as st, HealthCheck

import wlc
from wlc.main import Download

# Slugs come from the server; Weblate slugs are normally [-a-zA-Z0-9_], but the
# client must not trust them to stay inside --output.
seg = st.sampled_from(["..", ".", "a", "proj", "x_y", "/", "sub"])
slug = st.lists(seg, min_size=1, max_size=6).map("".join).filter(lambda s: s)


class FakeProject:
    def __init__(self, s):
        self.slug = s


class FakeComponent:
    def __init__(self, p, c):
        self.project = FakeProject(p)
        self.slug = c

    def download(self, convert):
        return b"PK"


@settings(max_examples=300, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(slug, slug)
def test_download_component_stays_in_output_dir(pslug, cslug):
    with tempfile.TemporaryDirectory() as root:
        out = Path(root) / "out" / "deep" / "deeper"
        cmd = Download.__new__(Download)
        cmd.args = Namespace(convert=None, output=str(out), no_glossary=False)
        written = []
        real_open = open

        def fake_open(path, mode="r", *a, **k):
            written.append(os.path.realpath(path))
            return real_open(os.devnull, mode)

        with mock.patch("builtins.open", fake_open), mock.patch("pathlib.Path.mkdir"):
            try:
                cmd.download_component(FakeComponent(pslug, cslug))
            except (IsADirectoryError, NotADirectoryError, FileNotFoundError):
                return
        for p in written:
            assert p.startswith(os.path.realpath(out) + os.sep), (pslug, cslug, p)


hostlabel = st.from_regex(r"[a-z][a-z0-9]{0,10}", fullmatch=True)


@given(hostlabel, st.sampled_from(["com", "net", "org", "io"]))
def test_ssl_verification_only_skipped_for_localhost(label, tld):
    url = f"https://127.0.0.1.{label}.{tld}/api/"
    assert wlc.Weblate._should_verify_ssl(url)


@given(hostlabel)
def test_token_not_sent_to_other_hosts(label):
    w = wlc.Weblate(key="SECRET", url="https://weblate.example.org/api/")
    assume_host = f"{label}.attacker.test"
    sent = {}

    def fake_request(method, path, **kw):
        sent["path"] = path
        sent["headers"] = kw["headers"]
        r = mock.Mock(status_code=200)
        r.json.return_value = {"results": [], "next": None}
        r.raise_for_status.return_value = None
        return r

    with mock.patch.object(w.session, "request", fake_request):
        w.get(f"https://{assume_host}/api/projects/")
    assert "Authorization" not in sent["headers"], sent

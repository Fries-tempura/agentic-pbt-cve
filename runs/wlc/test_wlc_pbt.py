import os
import string
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from hypothesis import given, settings, strategies as st

sys.path.insert(
    0,
    "/Users/auderyliu/Documents/NTU/project/agentic-pbt-main/dataset/checkouts/CVE-2026-22250__wlc",
)

import wlc  # noqa: E402
from wlc.main import Download  # noqa: E402

slug_chars = string.ascii_letters + string.digits + "-_./"
slugs = st.text(alphabet=slug_chars, min_size=1, max_size=20)


class FakeComponent:
    def __init__(self, project_slug, slug):
        self.project = SimpleNamespace(slug=project_slug)
        self.slug = slug

    def download(self, convert=None):
        return b"PK"


# Property 1: Download with --output DIR stores files inside DIR.
@settings(max_examples=500, deadline=None)
@given(slugs, slugs)
def test_download_component_stays_in_output_dir(project_slug, slug):
    with tempfile.TemporaryDirectory() as base:
        out = Path(base).resolve() / "a" / "b" / "out"
        cmd = Download.__new__(Download)
        cmd.args = SimpleNamespace(convert=None, output=str(out))
        written = []
        real_open = open

        def fake_open(path, mode="r", *a, **k):
            written.append(Path(path))
            return real_open(os.devnull, mode)

        with mock.patch("builtins.open", fake_open):
            try:
                cmd.download_component(FakeComponent(project_slug, slug))
            except OSError:
                return
        for p in written:
            resolved = Path(os.path.normpath(p))
            assert out in resolved.parents, (p, resolved)


# Property 2: SSL verification is only skipped for localhost.
hostnames = st.from_regex(r"\A[a-z][a-z0-9]{0,10}(\.[a-z][a-z0-9]{0,10}){1,3}\Z")


@settings(max_examples=300)
@given(hostnames)
def test_ssl_verified_for_non_localhost(host):
    url = f"https://127.0.0.1.{host}/api/"
    assert wlc.Weblate._should_verify_ssl(url), url


@given(hostnames)
def test_ssl_verified_for_plain_remote(host):
    assert wlc.Weblate._should_verify_ssl(f"https://{host}/api/")

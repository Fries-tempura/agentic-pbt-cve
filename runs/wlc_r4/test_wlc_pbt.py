import os, tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from hypothesis import given, settings, strategies as st, HealthCheck

import wlc
from wlc.main import Download

seg = st.text(alphabet=st.sampled_from(list("abc-_./")), min_size=1, max_size=12)


@settings(max_examples=500, suppress_health_check=list(HealthCheck))
@given(seg, seg)
def test_download_stays_in_output_dir(pslug, cslug):
    with tempfile.TemporaryDirectory() as root:
        out = Path(root) / "a" / "b" / "out"
        cmd = Download.__new__(Download)
        cmd.args = SimpleNamespace(output=str(out), convert=None, no_glossary=False)
        comp = SimpleNamespace(project=SimpleNamespace(slug=pslug), slug=cslug,
                               download=lambda convert: b"zip")
        written = []
        real_open = open
        def fake_open(p, mode="r", *a, **k):
            written.append(os.path.abspath(p))
            return real_open(os.devnull, mode)
        with mock.patch("builtins.open", fake_open):
            try:
                cmd.download_component(comp)
            except OSError:
                return
        for w in written:
            assert w.startswith(str(out.resolve()) + os.sep) or w.startswith(os.path.abspath(out) + os.sep), (pslug, cslug, w)


@given(st.from_regex(r"[a-z]{1,10}\.(com|org|net)", fullmatch=True))
def test_ssl_verified_for_remote_hosts(domain):
    assert wlc.Weblate._should_verify_ssl(f"https://{domain}/api/")
    assert wlc.Weblate._should_verify_ssl(f"https://127.0.0.1.{domain}/api/")


@settings(max_examples=50)
@given(st.from_regex(r"[a-z]{1,10}\.(com|org|net)", fullmatch=True))
def test_token_only_sent_to_configured_server(evil):
    w = wlc.Weblate(key="SECRET", url="https://weblate.example/api/")
    sent = []
    def fake_request(method, url, **kw):
        sent.append((url, kw["headers"].get("Authorization")))
        r = mock.Mock(status_code=200)
        r.raise_for_status = lambda: None
        r.json = lambda: {"results": [], "next": None} if "evil" in url or evil in url else {"results": [], "next": f"https://{evil}/steal/"}
        return r
    w.session.request = fake_request
    list(w.list_projects())
    for url, auth in sent:
        if not url.startswith("https://weblate.example/"):
            assert auth is None, (url, auth)

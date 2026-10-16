from unittest import mock
from urllib.parse import urlparse

import requests
from hypothesis import assume, given, settings, strategies as st

import wlc
from wlc.config import WeblateConfig

label = st.from_regex(r"[a-z][a-z0-9-]{0,10}[a-z0-9]", fullmatch=True)
domain = st.lists(label, min_size=1, max_size=4).map(".".join)


# Property 1: SSL verification is only disabled for localhost (127.0.0.1)
@given(suffix=st.one_of(domain.map(lambda d: "." + d), st.integers(0, 99).map(str)),
       path=st.from_regex(r"(/[a-z0-9]{0,8}){0,3}", fullmatch=True))
def test_ssl_verified_for_non_localhost(suffix, path):
    url = f"https://127.0.0.1{suffix}{path}"
    host = urlparse(url).hostname
    assume(host != "127.0.0.1")
    assert wlc.Weblate._should_verify_ssl(url), url


@given(host=domain, path=st.from_regex(r"(/[a-z0-9]{0,8}){0,3}", fullmatch=True))
def test_ssl_verified_for_remote_https(host, path):
    assert wlc.Weblate._should_verify_ssl(f"https://{host}{path}")


# Property 2: the API key (stored per server URL in config) is only sent to that server
class FakeResp:
    def __init__(self, data):
        self._data = data
        self.status_code = 200
        self.content = b""

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


@settings(max_examples=50)
@given(other=domain, key=st.from_regex(r"[A-Za-z0-9]{10,40}", fullmatch=True))
def test_key_not_leaked_to_other_host(other, key):
    assume(other != "weblate.example.com")
    w = wlc.Weblate(key=key, url="https://weblate.example.com/api/")
    pages = iter([
        {"results": [], "next": f"https://{other}/api/projects/?page=2"},
        {"results": [], "next": None},
    ])
    sent = []

    def fake_request(method, url, **kwargs):
        sent.append((url, kwargs["headers"]))
        return FakeResp(next(pages))

    with mock.patch.object(w.session, "request", side_effect=fake_request):
        list(w.list_projects())
    for url, headers in sent:
        if urlparse(url).hostname != "weblate.example.com":
            assert "Authorization" not in headers, (url, headers)


# Property 3: configured retries reach the HTTP adapter
@given(retries=st.integers(1, 20))
def test_retries_applied(retries):
    w = wlc.Weblate(url="https://x.example/api/", retries=retries)
    assert w.adapter.max_retries.total == retries


@given(retries=st.integers(1, 20))
def test_retries_applied_from_config(retries):
    c = WeblateConfig()
    c.set("weblate", "retries", str(retries))
    w = wlc.Weblate(config=c)
    assert w.adapter.max_retries.total == retries


# Property 4: default method whitelist is parsed into individual methods
def test_default_method_whitelist():
    c = WeblateConfig()
    methods = c.get_request_options()[2]
    assert all("\n" not in m for m in methods), methods

import hashlib
import ipaddress
import time

import pytest
from hypothesis import given, settings, HealthCheck, strategies as st

import eml_parser.regexes as R
from eml_parser.parser import EmlParser

ORIG_EMAIL_REGEX = R.email_regex


@pytest.fixture(autouse=True)
def restore_regex():
    R.email_regex = ORIG_EMAIL_REGEX
    yield
    R.email_regex = ORIG_EMAIL_REGEX


label = st.text(alphabet="abcdefghij0123456789", min_size=1, max_size=8)
domain = st.builds(lambda a, b: f"{a}.{b}", label, st.sampled_from(["com", "org", "net", "lu"]))
addr = st.builds(lambda u, d: f"{u}@{d}", label, domain)
subject = st.text(alphabet="abcdefghij ABC0123", min_size=1, max_size=20).map(str.strip).filter(bool)
body_text = st.text(alphabet="abc xyz.\n0123", max_size=200)


@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(frm=addr, tos=st.lists(addr, min_size=1, max_size=4), subj=subject, body=body_text)
def test_ignore_bad_start_noop_on_valid_message(frm, tos, subj, body):
    """CLAIM-1: ignore_bad_start does not change parsing of a message that starts with a header."""
    raw = f"From: {frm}\nTo: {', '.join(tos)}\nSubject: {subj}\n\n{body}\n".encode()
    a = EmlParser(include_raw_body=True).decode_email_bytes(raw)
    b = EmlParser(include_raw_body=True).decode_email_bytes(raw, ignore_bad_start=True)
    assert b['header'].get('from') == a['header']['from']
    assert b['header'].get('to') == a['header']['to']
    assert b['header'].get('subject') == a['header']['subject']
    assert [x['content'] for x in b['body']] == [x['content'] for x in a['body']]


@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(user=label, host=label)
def test_default_parser_unaffected_by_other_instance(user, host):
    """CLAIM-2: a default parser matches user@host regardless of earlier force_tld instances."""
    raw = f"From: a@b.com\n\nwrite to {user}@{host} now\n".encode()
    before = EmlParser(include_raw_body=True).decode_email_bytes(raw)['body'][0].get('email')
    EmlParser(email_force_tld=True)
    after = EmlParser(include_raw_body=True).decode_email_bytes(raw)['body'][0].get('email')
    assert before == after


@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(emails=st.lists(addr, min_size=1, max_size=4, unique=True))
def test_force_tld_received_email_are_addresses(emails):
    """CLAIM-3: with email_force_tld, received_email entries are e-mail addresses."""
    recv = "Received: from mx.example.com by mx2.example.org; " + " ".join(f"<{e}>" for e in emails) + "; Mon, 1 Jan 2024 00:00:00 +0000\n"
    raw = ("From: a@b.com\n" + recv + "\nx\n").encode()
    got = EmlParser(email_force_tld=True).decode_email_bytes(raw)['header'].get('received_email', [])
    R.email_regex = ORIG_EMAIL_REGEX
    want = EmlParser().decode_email_bytes(raw)['header'].get('received_email', [])
    assert sorted(got) == sorted(want)
    assert all('@' in e for e in got)


class Tracked(str):
    def __getitem__(self, k):
        r = str.__getitem__(self, k)
        if isinstance(k, slice):
            r = _Slice(r)
            r.bounds = k.indices(len(self))[:2]
        return r


class _Slice(str):
    pass


@settings(max_examples=1000)
@given(body=st.lists(st.sampled_from(["a", "b", " ", "\n", ".", "/", ":", ">", "://", "http://"]), max_size=800).map("".join),
       step=st.integers(min_value=10, max_value=600), dist=st.integers(min_value=1, max_value=200))
def test_sliding_window_covers_body(body, step, dist):
    """CLAIM-4: every index of body is covered by some yielded slice; generator terminates."""
    covered = [False] * len(body)
    n = 0
    for sl in EmlParser.string_sliding_window_loop(Tracked(body), slice_step=step, max_distance=dist):
        n += 1
        assert n < 10 * (len(body) // step + 2)
        if hasattr(sl, "bounds"):
            a, b = sl.bounds
            for i in range(a, b):
                covered[i] = True
        else:
            covered = [True] * len(body)
    missing = [i for i, c in enumerate(covered) if not c]
    assert not missing, (missing[:10], [body[i] for i in missing[:20]])


@given(v=st.one_of(st.binary(), st.text()), t=st.sampled_from(['md5', 'sha1', 'sha256', 'sha512']))
def test_get_hash_reference(v, t):
    """CLAIM-5: get_hash matches hashlib."""
    b = v.encode('utf-8') if isinstance(v, str) else v
    assert EmlParser.get_hash(v, t) == hashlib.new(t, b).hexdigest()


@given(ip=st.one_of(st.ip_addresses(v=4), st.ip_addresses(v=6)), user=label)
def test_valid_ip(ip, user):
    """CLAIM-6: valid IPs are returned in canonical form, also after user@."""
    p = EmlParser()
    assert p.get_valid_domain_or_ip(str(ip)) == str(ip)
    assert p.get_valid_domain_or_ip(f"{user}@{ip}") == str(ip)


@settings(max_examples=5, deadline=None)
@given(ch=st.sampled_from("a1.-_"))
def test_received_header_linear(ch):
    """CLAIM-7: parse time grows ~linearly with Received header length."""
    def run(n):
        raw = b"From: a@b.com\nReceived: from " + ch.encode() * n + b"\n\nx\n"
        s = time.perf_counter()
        EmlParser().decode_email_bytes(raw)
        return time.perf_counter() - s
    run(1000)
    t1, t2 = run(20000), run(40000)
    assert t2 < 3 * t1 + 0.05, (t1, t2)


hdr_name = st.sampled_from(["From", "To", "Cc", "Subject", "Date", "Received", "Message-ID", "Content-Type", "Content-Disposition", "Content-Transfer-Encoding", "X-Foo"])
hdr_val = st.lists(st.sampled_from(list("ab@.<>[]()\";:,=?/ 0123") + ["=?utf-8?b?", "=?utf-8?q?", "?=", "multipart/mixed", "boundary=", "text/html", "base64", "attachment", "filename="]), max_size=40).map("".join)


@settings(max_examples=500, deadline=None)
@given(headers=st.lists(st.tuples(hdr_name, hdr_val), max_size=8), body=st.text(alphabet="ab@.:/ \n-=", max_size=200))
def test_no_crash(headers, body):
    """CLAIM-8: decode_email_bytes does not raise on malformed but e-mail-like input."""
    raw = "".join(f"{k}: {v}\n" for k, v in headers) + "\n" + body
    EmlParser().decode_email_bytes(raw.encode("utf-8"))

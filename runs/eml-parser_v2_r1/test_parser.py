import hashlib
import ipaddress
import time

from hypothesis import given, settings, strategies as st, HealthCheck

from eml_parser.parser import EmlParser

local = st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEF0123456789._-", min_size=1, max_size=8).filter(
    lambda s: s[0] not in '.-' and s[-1] not in '.' and '..' not in s
)
label = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=8)
addr = st.builds(lambda l, d, t: f"{l}@{d}.{t}", local, label, st.sampled_from(["com", "org", "net", "lu"]))
subject = st.text(alphabet="abcdefghij XYZ0123", min_size=1, max_size=20).map(str.strip).filter(bool)
body_txt = st.text(alphabet="abcdefg hij\n.:/@0123", max_size=200)


def build(frm, tos, subj, body):
    return (f"From: {frm}\nTo: {', '.join(tos)}\nSubject: {subj}\n\n{body}\n").encode()


def summary(r):
    return r["header"]["header"], [b.get("content") for b in r["body"]]


@settings(max_examples=200)
@given(addr, st.lists(addr, min_size=1, max_size=4), subject, body_txt)
def test_ignore_bad_start_noop_on_valid(frm, tos, subj, body):
    """CLAIM-1: ignore_bad_start does not alter a well-formed email."""
    e = build(frm, tos, subj, body)
    p = EmlParser(include_raw_body=True)
    assert summary(p.decode_email_bytes(e, ignore_bad_start=True)) == summary(p.decode_email_bytes(e))


@settings(max_examples=200)
@given(st.lists(st.text(alphabet="abc xyz", min_size=1, max_size=10), min_size=1, max_size=3),
       addr, st.lists(addr, min_size=1, max_size=3), subject, body_txt)
def test_ignore_bad_start_skips_junk(junk, frm, tos, subj, body):
    """CLAIM-2: leading junk lines are skipped, rest parsed as without junk."""
    e = build(frm, tos, subj, body)
    j = ("\n".join(junk) + "\n").encode()
    p = EmlParser(include_raw_body=True)
    assert p.decode_email_bytes(j + e, ignore_bad_start=True)["header"]["header"] == p.decode_email_bytes(e)["header"]["header"]


@settings(max_examples=500)
@given(st.text(alphabet="ab :/.> \nh", min_size=0, max_size=3000), st.integers(20, 600), st.integers(1, 120))
def test_sliding_window_covers(body, step, dist):
    """CLAIM-3: every character of body is covered by some yielded slice."""
    class Rec(str):
        last = None

        def __getitem__(self, k):
            if isinstance(k, slice):
                Rec.last = k
            return str.__getitem__(self, k)

    covered = [False] * len(body)
    rb = Rec(body)
    for s in EmlParser.string_sliding_window_loop(rb, step, dist):
        if len(body) <= step:
            covered = [True] * len(body)
            break
        # the yielded value is body[ptr_start:ptr_end], the last slice taken before the yield
        a, b = Rec.last.start, Rec.last.stop
        assert s == body[a:b]
        for k in range(max(a, 0), min(b, len(body))):
            covered[k] = True
    assert all(covered), covered.index(False)


@given(st.one_of(st.binary(), st.text()), st.sampled_from(["md5", "sha1", "sha256", "sha512"]))
def test_get_hash_reference(v, t):
    """CLAIM-4: get_hash matches hashlib."""
    b = v.encode() if isinstance(v, str) else v
    assert EmlParser.get_hash(v, t) == hashlib.new(t, b).hexdigest()


@given(st.one_of(st.ip_addresses(v=4), st.ip_addresses(v=6)))
def test_valid_ip(ip):
    """CLAIM-5: IP addresses are returned in canonical form."""
    assert EmlParser().get_valid_domain_or_ip(str(ip)) == str(ip)


@settings(max_examples=200)
@given(addr, st.lists(addr, min_size=1, max_size=6), subject)
def test_to_list(frm, tos, subj):
    """CLAIM-6: To header addresses all returned, lowercased, in order."""
    r = EmlParser().decode_email_bytes(build(frm, tos, subj, "x"))
    assert r["header"]["to"] == [a.lower() for a in tos]


@settings(max_examples=500, suppress_health_check=list(HealthCheck))
@given(st.binary(max_size=600) | st.text(alphabet="abc:\n =?-Content-Type multipart/mixed;boundary\"x\"--", max_size=600).map(str.encode))
def test_no_crash(b):
    """CLAIM-7: decode_email_bytes returns a dict or raises RecursionError."""
    try:
        assert isinstance(EmlParser().decode_email_bytes(b), dict)
    except RecursionError:
        pass


def _t(e):
    t = time.perf_counter()
    EmlParser(include_raw_body=True).decode_email_bytes(e)
    return time.perf_counter() - t


@settings(max_examples=15, deadline=None)
@given(st.sampled_from(["a", "a.", "a-", "www.", "1.", "http://a", "/", "x@"]), st.sampled_from(["body", "received", "subject"]))
def test_linear_cost(unit, where):
    """CLAIM-8: doubling input size does not more than ~3x the time."""
    def mk(n):
        s = unit * n
        if where == "body":
            return f"From: a@b.com\nSubject: s\n\nhttp://{s}\n".encode()
        if where == "received":
            return f"Received: from {s} by x\nFrom: a@b.com\n\nx\n".encode()
        return f"Subject: {s}\nFrom: a@b.com\n\nx\n".encode()
    n = 4000
    t1, t2 = _t(mk(n)), _t(mk(2 * n))
    assert t2 < 1.0 or t2 < 3 * t1, (unit, where, t1, t2)

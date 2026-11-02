import hashlib
import ipaddress
import time

from hypothesis import given, settings, strategies as st, HealthCheck

from eml_parser.parser import EmlParser

atom = st.text(alphabet="abcdefghijklmnopqrstuvwxyzABC0123456789", min_size=1, max_size=8)
addr = st.builds(lambda l, d, t: f"{l}@{d}.{t}", atom, atom, st.sampled_from(["com", "org", "lu"]))
junk_line = st.text(alphabet="abc xyz-_=!.0123456789", min_size=0, max_size=20)


def _headers(r):
    h = r["header"]
    return h.get("from"), h.get("to"), h.get("subject"), h.get("header")


@given(frm=addr, to=st.lists(addr, min_size=1, max_size=4), subj=atom,
       junk=st.lists(junk_line, min_size=0, max_size=3))
@settings(max_examples=200)
def test_ignore_bad_start(frm, to, subj, junk):
    """CLAIM-1: skipping an invalid start leaves the e-mail's headers intact."""
    eml = f"From: {frm}\nTo: {', '.join(to)}\nSubject: {subj}\n\nbody\n".encode()
    prefix = b"".join(j.encode() + b"\n" for j in junk)
    ref = EmlParser().decode_email_bytes(eml)
    got = EmlParser().decode_email_bytes(prefix + eml, ignore_bad_start=True)
    assert _headers(got) == _headers(ref)


def _time(raw):
    p = EmlParser()
    s = time.perf_counter()
    p.decode_email_bytes(raw)
    return time.perf_counter() - s


@given(ch=st.sampled_from(["a", "a.", "x-", "1"]))
@settings(max_examples=4, deadline=None, suppress_health_check=list(HealthCheck))
def test_received_linear(ch):
    """CLAIM-2: Received-header parsing cost scales linearly."""
    n = 16000 // len(ch)
    t1 = _time(b"Received: from " + (ch * n).encode() + b"\n\nhi\n")
    t2 = _time(b"Received: from " + (ch * 4 * n).encode() + b"\n\nhi\n")
    assert t2 < 1.0, (t1, t2)
    assert t2 / max(t1, 1e-3) < 8, (t1, t2)


@given(v=st.one_of(st.text(), st.binary()), t=st.sampled_from(["md5", "sha1", "sha256", "sha512"]))
def test_get_hash(v, t):
    """CLAIM-3: get_hash agrees with hashlib."""
    b = v.encode() if isinstance(v, str) else v
    assert EmlParser.get_hash(v, t) == hashlib.new(t, b).hexdigest()


@given(ip=st.one_of(st.ip_addresses(v=4), st.ip_addresses(v=6)))
def test_valid_ip(ip):
    """CLAIM-4: IPs (bare, or as user@[ip]) are returned as their string form."""
    p = EmlParser()
    assert p.get_valid_domain_or_ip(str(ip)) == str(ip)
    assert p.get_valid_domain_or_ip(f"x@[{ip}]") == str(ip)


@given(to=st.lists(addr, min_size=1, max_size=6))
def test_headeremail2list(to):
    """CLAIM-5: To addresses come back lowercased, one per address, in order."""
    p = EmlParser()
    p.decode_email_bytes(f"To: {', '.join(to)}\n\nx\n".encode())
    assert p.headeremail2list("to") == [a.lower() for a in to]


hdr = st.builds(lambda n, v: f"{n}: {v}".encode(),
                st.sampled_from(["From", "To", "Cc", "Subject", "Date", "Received", "Message-ID",
                                 "Content-Type", "Content-Transfer-Encoding", "Content-Disposition"]),
                st.text(alphabet=st.characters(codec="latin-1", exclude_characters="\r\n"), max_size=40))


@given(hs=st.lists(hdr, max_size=6), body=st.binary(max_size=200))
@settings(max_examples=500)
def test_no_crash(hs, body):
    """CLAIM-6: decode_email_bytes does not raise on arbitrary header/body input."""
    raw = b"\n".join(hs) + b"\n\n" + body
    assert isinstance(EmlParser().decode_email_bytes(raw), dict)


@given(body=st.text(alphabet="ab :/.> \n", min_size=0, max_size=3000),
       step=st.integers(20, 600), md=st.integers(1, 150))
@settings(max_examples=500)
def test_sliding_window_coverage(body, step, md):
    """CLAIM-7: the yielded slices jointly cover the body."""
    covered = [False] * len(body)
    pos = 0
    for s in EmlParser.string_sliding_window_loop(body, step, md):
        if not s:
            continue
        i = body.find(s, max(0, pos - 200))
        assert i >= 0
        for k in range(i, i + len(s)):
            covered[k] = True
        pos = i + len(s)
    assert all(covered)

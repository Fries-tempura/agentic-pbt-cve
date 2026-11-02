import ipaddress
import time

from hypothesis import given, settings, strategies as st, HealthCheck

import eml_parser
from eml_parser.parser import EmlParser

local = st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJ0123456789._-", min_size=1, max_size=8).filter(
    lambda s: s[0].isalnum() and s[-1].isalnum() and ".." not in s
)
label = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=8)
domain = st.builds(lambda a, b: f"{a}.{b}", label, st.sampled_from(["com", "org", "net", "lu"]))
addr = st.builds(lambda l, d: f"{l}@{d}", local, domain)
words = st.text(alphabet="abc xyz.:/@\n0123", max_size=60)


def strip_uuid(res):
    body = [{k: v for k, v in b.items()} for b in res["body"]]
    h = dict(res["header"])
    return body, h


def build_email(frm, to, subject, body):
    return (f"From: {frm}\nTo: {', '.join(to)}\nSubject: {subject}\nContent-Type: text/plain\n\n{body}\n").encode()


@settings(max_examples=200)
@given(frm=addr, to=st.lists(addr, min_size=1, max_size=4), subject=st.text("abc def", max_size=10),
       body=words, junk=st.lists(st.text("abc xyz 012!", max_size=10), max_size=3))
def test_ignore_bad_start(frm, to, subject, body, junk):
    """CLAIM-1: ignore_bad_start only skips leading junk lines; rest of the parse is unchanged."""
    e = build_email(frm, to, subject, body)
    p = EmlParser(include_raw_body=True)
    ref = strip_uuid(p.decode_email_bytes(e))
    prefix = b"".join(j.encode() + b"\n" for j in junk)
    got = strip_uuid(EmlParser(include_raw_body=True).decode_email_bytes(prefix + e, ignore_bad_start=True))
    assert got == ref


@settings(max_examples=100)
@given(payloads=st.lists(st.binary(min_size=1, max_size=20), min_size=1, max_size=6))
def test_unnamed_attachment_names_distinct(payloads):
    """CLAIM-2: N unnamed attachments get N distinct generated filenames."""
    import base64
    parts = [b"From: a@b.com\nMIME-Version: 1.0\nContent-Type: multipart/mixed; boundary=XX\n\n"]
    for pl in payloads:
        parts.append(b"--XX\nContent-Type: application/octet-stream\nContent-Transfer-Encoding: base64\n\n"
                     + base64.b64encode(pl) + b"\n")
    parts.append(b"--XX--\n")
    res = EmlParser().decode_email_bytes(b"".join(parts))
    names = [a["filename"] for a in res["attachment"]]
    assert len(names) == len(payloads)
    assert len(set(names)) == len(names), names


@settings(max_examples=300)
@given(body=st.text(alphabet="ab :/.", min_size=0, max_size=3000))
def test_window_covers_body(body):
    """CLAIM-3a: every character of the body lies in some yielded slice."""
    covered = [False] * len(body)
    # recover positions: slices are substrings at increasing positions; track via index search
    slices = list(EmlParser.string_sliding_window_loop(body))
    joined_ok = True
    pos = 0
    for s in slices:
        if not s:
            continue
        i = body.find(s, max(0, pos - 16 - len(s)))
        assert i != -1
        for k in range(i, i + len(s)):
            covered[k] = True
        pos = i + len(s)
    assert all(covered), (len(body), [len(s) for s in slices])


@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(offset=st.integers(0, 1600), host=label, path=st.text("abcdef0123", min_size=1, max_size=20))
def test_url_not_cut(offset, host, path):
    """CLAIM-3b: a short URL anywhere in a long body is reported intact."""
    url = f"http://{host}.com/{path}"
    body = "x " * (offset // 2) + ("x" if offset % 2 else "") + " " + url + " " + "y " * 600
    e = f"From: a@b.com\nContent-Type: text/plain\n\n{body}\n".encode()
    res = EmlParser(include_raw_body=True).decode_email_bytes(e)
    assert url in res["body"][0].get("uri", []), res["body"][0].get("uri")


@given(a=st.one_of(st.ip_addresses(v=4), st.ip_addresses(v=6)))
def test_valid_ip(a):
    """CLAIM-4: IPs (bare and as e-mail host) are returned canonically."""
    p = EmlParser()
    assert p.get_valid_domain_or_ip(str(a)) == str(a)
    assert p.get_valid_domain_or_ip("x@" + str(a)) == str(a)


@given(to=st.lists(addr, min_size=1, max_size=6))
def test_to_list(to):
    """CLAIM-5: headeremail2list returns lower-cased addr-specs of the header."""
    res = EmlParser().decode_email_bytes(build_email("a@b.com", to, "s", "b"))
    assert res["header"]["to"] == [a.lower() for a in to]


@settings(max_examples=300)
@given(hdrs=st.lists(st.tuples(st.sampled_from(["From", "To", "Cc", "Subject", "Date", "Received", "Message-ID",
                                                 "Content-Type", "Content-Disposition", "X-A"]),
                               st.text(alphabet="abc@<>[]\"(),;:=?.-_ 0123\\/", max_size=40)), max_size=8),
       body=st.binary(max_size=60))
def test_no_crash(hdrs, body):
    """CLAIM-6: decode_email_bytes doesn't raise undocumented exceptions."""
    raw = b"".join(f"{k}: {v}\n".encode() for k, v in hdrs) + b"\n" + body
    EmlParser().decode_email_bytes(raw)


@settings(max_examples=10, deadline=None)
@given(ch=st.sampled_from(["a", "1", "from ", "a.", "-"]))
def test_received_header_cost(ch):
    """CLAIM-7: parse time roughly linear in Received header length."""
    def run(n):
        raw = b"From: a@b.com\nReceived: " + (ch * n).encode() + b"\nSubject: x\n\nhi"
        s = time.perf_counter()
        EmlParser().decode_email_bytes(raw)
        return time.perf_counter() - s
    t = run(100_000 // len(ch))
    assert t < 1.0, f"{ch!r}: {t:.2f}s for 100KB Received header"

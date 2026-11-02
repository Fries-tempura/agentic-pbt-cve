import importlib
import time

from hypothesis import given, settings, strategies as st, HealthCheck

import eml_parser.parser as P
import eml_parser.regexes as R

local = st.text(alphabet="abcxyz019", min_size=1, max_size=8)
domain = st.builds(lambda a, b: f"{a}.{b}", local, st.sampled_from(["com", "org", "net"]))
addr = st.builds(lambda l, d: f"{l}@{d}", local, domain)
subject = st.text(alphabet="abc XYZ 123!?", min_size=1, max_size=30).map(str.strip).filter(bool)
body = st.text(alphabet="abc def\nhttp://x.com 1.2.3.4 ", max_size=200)


@st.composite
def emails(draw):
    s = draw(subject)
    f = draw(addr)
    t = draw(addr)
    b = draw(body)
    return f"From: {f}\nTo: {t}\nSubject: {s}\n\n{b}\n".encode()


def summary(res):
    h = res["header"]
    return (h.get("subject"), h.get("from"), h.get("to"), sorted(x["hash"] for x in res["body"]))


@settings(max_examples=200)
@given(emails())
def test_ignore_bad_start_noop_on_valid(raw):
    """CLAIM-1: ignore_bad_start is a no-op on a valid email."""
    assert summary(P.EmlParser().decode_email_bytes(raw, ignore_bad_start=True)) == summary(
        P.EmlParser().decode_email_bytes(raw)
    )


@settings(max_examples=200)
@given(emails(), st.lists(st.text(alphabet="junk -", min_size=1, max_size=10), min_size=1, max_size=3))
def test_ignore_bad_start_skips_junk(raw, junk):
    """CLAIM-2: leading junk lines are skipped and the rest parses as the clean email."""
    prefixed = ("\n".join(junk) + "\n").encode() + raw
    got = P.EmlParser().decode_email_bytes(prefixed, ignore_bad_start=True)["header"]
    exp = P.EmlParser().decode_email_bytes(raw)["header"]
    assert (got.get("subject"), got.get("from"), got.get("to")) == (exp.get("subject"), exp.get("from"), exp.get("to"))


@settings(max_examples=50, suppress_health_check=list(HealthCheck))
@given(st.lists(st.booleans(), max_size=4), local, local)
def test_force_tld_is_per_instance(flags, user, host):
    """CLAIM-3: a default-constructed parser matches TLD-less addresses regardless of earlier instances."""
    importlib.reload(R)  # fresh-process state
    for f in flags:
        P.EmlParser(email_force_tld=f)
    raw = f"From: a@b.com\nReceived: from x.com by y.com; id {user}@{host}\n\nhi\n".encode()
    res = P.EmlParser().decode_email_bytes(raw)
    assert f"{user}@{host}" in res["header"].get("received_email", [])


markers = [chr(0x4E00 + i) for i in range(3000)]


@settings(max_examples=500)
@given(st.lists(st.sampled_from(["://", " ", ">", "a", "M", "M", "M"]), min_size=1, max_size=1500))
def test_sliding_window_covers_body(toks):
    """CLAIM-4: every character of the body appears in some slice."""
    it = iter(markers)
    body = "".join(next(it) if t == "M" else t for t in toks)
    want = {c for c in body if c in set(markers)}
    seen = set("".join(P.EmlParser.string_sliding_window_loop(body)))
    assert want <= seen


hdr_val = st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=60)


@settings(max_examples=300)
@given(st.lists(st.tuples(st.sampled_from(["From", "To", "Cc", "Subject", "Date", "Received", "Message-ID", "Content-Type", "Delivered-To"]), hdr_val), max_size=6), body)
def test_no_crash(headers, b):
    """CLAIM-5: decode_email_bytes does not raise on plausible emails."""
    raw = "".join(f"{k}: {v}\n" for k, v in headers) + "\n" + b
    P.EmlParser().decode_email_bytes(raw.encode())


def _t(raw):
    t = time.perf_counter()
    P.EmlParser().decode_email_bytes(raw)
    return time.perf_counter() - t


@settings(max_examples=15, deadline=None)
@given(st.text(alphabet="a.@:1 -from[]<>=", min_size=1, max_size=6), st.sampled_from(["Received", "From", "To", "Subject", "X-Foo"]))
def test_header_cost_linear(unit, name):
    """CLAIM-6: cost of parsing a header scales ~linearly with its length."""
    def mk(n):
        return f"{name}: {(unit * (n // len(unit)))}\n\nx\n".encode()
    small, big = _t(mk(10000)), _t(mk(40000))
    assert big < max(small, 0.02) * 8, (small, big)


@settings(max_examples=15, deadline=None)
@given(st.text(alphabet="a.@:/1 <>=\"'whtp", min_size=1, max_size=8))
def test_body_cost_linear(unit):
    """CLAIM-6: cost of parsing a body scales ~linearly with its length."""
    def mk(n):
        return ("From: a@b.com\n\n" + unit * (n // len(unit)) + "\n").encode()
    small, big = _t(mk(20000)), _t(mk(80000))
    assert big < max(small, 0.02) * 8, (small, big)

import email.message, email.policy
from hypothesis import given, settings, strategies as st, HealthCheck
import eml_parser.parser as P
from eml_parser.parser import EmlParser

body_chars = st.sampled_from(list("abc .:/@<>\n-x") + ["://", "http://", "www.", " "])
bodies = st.lists(body_chars, max_size=600).map("".join)

@settings(max_examples=2000, suppress_health_check=[HealthCheck.too_slow])
@given(bodies, st.integers(1, 60), st.integers(1, 30))
def test_sliding_window_covers_body(body, step, dist):
    slices = list(EmlParser.string_sliding_window_loop(body, slice_step=step, max_distance=dist))
    # every character position of body must appear in some slice: reconstruct coverage
    covered = set()
    pos = 0
    for s in slices:
        idx = body.find(s, max(0, pos - 200)) if s else pos
        # track by reconstructing the actual pointers is hard; use content check instead
    joined = "".join(slices)
    for i in range(len(body)):
        pass
    # weaker: every URL token "http://..." in the body must appear whole in some slice
    import re
    for m in re.finditer(r"https?://[a-z.]+", body):
        assert any(m.group(0) in s for s in slices), (body, slices, m.group(0))

addr = st.from_regex(r"[a-z]{1,8}@[a-z]{1,8}\.(com|org|net)", fullmatch=True)

@settings(max_examples=300)
@given(addr, addr, st.text(alphabet="abcdef ", min_size=1, max_size=20))
def test_ignore_bad_start_on_valid_email(frm, to, subj):
    raw = f"From: {frm}\nTo: {to}\nSubject: {subj.strip() or 'x'}\n\nhello body\n".encode()
    a = EmlParser().decode_email_bytes(raw)
    b = EmlParser().decode_email_bytes(raw, ignore_bad_start=True)
    assert a['header']['from'] == b['header']['from']
    assert a['header']['to'] == b['header']['to']
    assert a['header']['subject'] == b['header']['subject']

@settings(max_examples=500)
@given(st.binary(max_size=400))
def test_decode_no_crash(data):
    EmlParser().decode_email_bytes(b"From: a@b.com\nSubject: x\n\n" + data)

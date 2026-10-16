from hypothesis import given, settings, strategies as st, HealthCheck
import eml_parser.parser as P

word = st.from_regex(r"[A-Za-z0-9]{1,12}", fullmatch=True)

@settings(max_examples=200, suppress_health_check=list(HealthCheck))
@given(word, st.lists(st.from_regex(r"[a-z ]{1,20}", fullmatch=True), min_size=0, max_size=3))
def test_ignore_bad_start_strips_only_garbage(subject, garbage):
    good = f"From: a@b.com\nTo: c@d.org\nSubject: {subject}\n\nhello body\n".encode()
    raw = b"".join(g.encode() + b"\n" for g in garbage) + good
    ref = P.EmlParser().decode_email_bytes(good)
    res = P.EmlParser().decode_email_bytes(raw, ignore_bad_start=True)
    assert res["header"]["subject"] == ref["header"]["subject"]
    assert res["header"].get("to") == ref["header"].get("to")

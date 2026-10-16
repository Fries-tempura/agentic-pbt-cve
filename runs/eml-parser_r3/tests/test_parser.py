import datetime
from hypothesis import given, settings, strategies as st, HealthCheck
import eml_parser
from eml_parser.parser import EmlParser


class Sl(str):
    pass


class Tracking(str):
    def __getitem__(self, k):
        r = Sl(str.__getitem__(self, k))
        if isinstance(k, slice):
            r.rng = k.indices(len(self))[:2]
        return r


body_chars = st.sampled_from(list("abc. \n>:/@") + ["://", "http://x.com/", " "])


@settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(body_chars, max_size=600).map("".join), st.integers(10, 200), st.integers(1, 100))
def test_sliding_window_covers_body(body, step, maxd):
    tb = Tracking(body)
    covered = set()
    for s in EmlParser.string_sliding_window_loop(tb, slice_step=step, max_distance=maxd):
        if hasattr(s, "rng"):
            covered.update(range(*s.rng))
        else:
            covered.update(range(len(body)))
    assert covered >= set(range(len(body))), sorted(set(range(len(body))) - covered)[:10]


hdr_val = st.text(st.characters(min_codepoint=32, max_codepoint=126), max_size=30).map(str.strip)
words = st.text(st.sampled_from("abcdefg .,:/@<>\n"), max_size=200)


@settings(max_examples=300)
@given(hdr_val, words)
def test_ignore_bad_start_noop_on_valid_email(subject, body):
    raw = (f"From: alice@example.com\nTo: bob@example.org\nSubject: {subject}\n"
           f"Date: Mon, 1 Jan 2024 10:00:00 +0000\n\n{body}").encode()
    p = EmlParser(include_raw_body=True)
    a = p.decode_email_bytes(raw)
    b = p.decode_email_bytes(raw, ignore_bad_start=True)
    assert a["header"]["subject"] == b["header"]["subject"]
    assert a["header"]["to"] == b["header"]["to"]
    assert a["header"]["from"] == b["header"]["from"]


@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.tuples(st.sampled_from(["From", "To", "Cc", "Subject", "Date", "Received", "Message-ID",
                                           "Content-Type", "Content-Disposition", "Content-Transfer-Encoding", "X-Foo"]),
                          st.text(st.characters(min_codepoint=1, max_codepoint=0x2fff, blacklist_characters="\r\n"), max_size=40)),
                max_size=8),
       st.binary(max_size=300))
def test_decode_email_bytes_no_crash(headers, body):
    raw = b"".join(f"{k}: {v}\n".encode("utf-8") for k, v in headers) + b"\n" + body
    r = EmlParser(include_raw_body=True).decode_email_bytes(raw)
    assert isinstance(r["header"]["date"], datetime.datetime)

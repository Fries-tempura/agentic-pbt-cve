from hypothesis import given, settings, strategies as st, HealthCheck
import eml_parser.parser as P

hdr = st.sampled_from(["From", "To", "Cc", "Delivered-To", "Subject", "Date", "Received", "Message-ID", "Content-Type", "Content-Disposition", "Reply-To", "Sender"])
atoms = st.sampled_from(["<", ">", "@", "[", "]", ",", ";", ":", "\"", "(", ")", "\\", "=?utf-8?q?", "=?utf-8?b?", "?=", "a@b.com", "<x@[1.2.3.4]>", "by mx.example.com", "from host", "for <u@v.org>", " ", "\n ", "Mon, 1 Jan 2001 00:00:00 +0000", "1.2.3.4", "::1", "\udcff", "é", "\x00", "=?", "%", "grp:"])
val = st.lists(atoms, max_size=15).map("".join)

@settings(max_examples=3000, suppress_health_check=list(HealthCheck), deadline=None)
@given(st.lists(st.tuples(hdr, val), max_size=6))
def test_headers_no_crash(headers):
    raw = "".join(f"{k}: {v}\n" for k, v in headers) + "\nbody\n"
    P.EmlParser().decode_email_bytes(raw.encode("utf-8", "surrogateescape"))

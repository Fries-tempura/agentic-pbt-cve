from hypothesis import given, settings, strategies as st, HealthCheck
from eml_parser.parser import EmlParser
val = st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\r\n"), max_size=60)
names = st.sampled_from(["From", "To", "Cc", "Date", "Subject", "Received", "Message-ID", "Content-Type", "Content-Disposition", "Delivered-To", "Content-Transfer-Encoding"])
@settings(max_examples=1500, suppress_health_check=list(HealthCheck))
@given(st.lists(st.tuples(names, val), max_size=8), st.text(max_size=200))
def test_headers_no_crash(hdrs, body):
    raw = "".join(f"{k}: {v}\n" for k, v in hdrs) + "\n" + body
    EmlParser(include_raw_body=True, include_attachment_data=True).decode_email_bytes(raw.encode("utf-8", "surrogatepass"))

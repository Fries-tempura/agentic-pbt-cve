import time
from eml_parser.parser import EmlParser

for n in (25_000, 50_000, 100_000):
    raw = b"From: a@b.com\nReceived: from " + b"a" * n + b"\n\nx\n"
    t = time.perf_counter()
    EmlParser().decode_email_bytes(raw)
    print(n, round(time.perf_counter() - t, 2), "s")

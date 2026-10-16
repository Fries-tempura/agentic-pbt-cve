from eml_parser import EmlParser

raw = b"From: alice@example.com\nTo: bob@example.org\nSubject: hello\n\nbody text\n"
p = EmlParser()
print(p.decode_email_bytes(raw)["header"]["to"], p.decode_email_bytes(raw)["header"]["subject"])
r = p.decode_email_bytes(raw, ignore_bad_start=True)
print(r["header"]["to"], repr(r["header"]["subject"]), r["header"]["header"])

raw2 = b"garbage line\nFrom: alice@example.com\nTo: bob@example.org\nSubject: hello\n\nbody\n"
r = p.decode_email_bytes(raw2, ignore_bad_start=True)
print(r["header"]["to"], repr(r["header"]["subject"]), r["header"]["header"])

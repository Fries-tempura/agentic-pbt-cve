import eml_parser
raw = b"From: a@b.com\nTo: c@d.org\nSubject: hi\n\nhello body\n"
p = eml_parser.EmlParser()
print(p.decode_email_bytes(raw)["header"]["subject"], p.decode_email_bytes(raw)["header"]["to"])
r = p.decode_email_bytes(raw, ignore_bad_start=True)
print(repr(r["header"]["subject"]), r["header"]["to"], r["header"]["header"])

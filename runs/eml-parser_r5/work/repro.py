from eml_parser.parser import EmlParser
raw = b"Subject: hello\nTo: bob@example.com\n\nbody text\n"
p = EmlParser(include_raw_body=True)
a = p.decode_email_bytes(raw)
b = p.decode_email_bytes(raw, ignore_bad_start=True)
print(a['header']['header'], a['body'][0]['content'])
print(b['header']['header'], b['body'][0]['content'] if b['body'] else None)

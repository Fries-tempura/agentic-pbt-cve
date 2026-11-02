from eml_parser.parser import EmlParser

raw = b"From: a@b.com\n\nwrite to john@doe\n"
print(EmlParser(include_raw_body=True).decode_email_bytes(raw)['body'][0].get('email'))
EmlParser(email_force_tld=True)
print(EmlParser(include_raw_body=True).decode_email_bytes(raw)['body'][0].get('email'))

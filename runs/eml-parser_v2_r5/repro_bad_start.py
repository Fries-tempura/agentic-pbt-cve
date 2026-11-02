from eml_parser.parser import EmlParser

raw = b"From: alice@example.com\nTo: bob@example.org\nSubject: hi\n\nhello\n"
a = EmlParser().decode_email_bytes(raw)
b = EmlParser().decode_email_bytes(raw, ignore_bad_start=True)
print(a['header']['from'], a['header']['to'], a['header']['subject'])
print(b['header'].get('from'), b['header'].get('to'), b['header'].get('subject'))
assert b['header']['from'] == a['header']['from']

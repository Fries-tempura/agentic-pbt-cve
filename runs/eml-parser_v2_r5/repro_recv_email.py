from eml_parser.parser import EmlParser

raw = b"From: a@b.com\nReceived: from mx.example.com by mx2.example.org; <alice@example.com>; Mon, 1 Jan 2024 00:00:00 +0000\n\nx\n"
print(EmlParser(email_force_tld=True).decode_email_bytes(raw)['header']['received_email'])

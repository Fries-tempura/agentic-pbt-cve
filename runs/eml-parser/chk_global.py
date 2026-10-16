import eml_parser
import eml_parser.regexes

raw = b"""From: a@b.com
Subject: t
Content-Type: text/plain

contact john@doe here
"""

p = eml_parser.EmlParser(include_raw_body=True)
before = p.decode_email_bytes(raw)['body'][0].get('email')

other = eml_parser.EmlParser(email_force_tld=True)  # unrelated instance

after = p.decode_email_bytes(raw)['body'][0].get('email')
print('before:', before)
print('after :', after)
print('regex is force_tld now:', eml_parser.regexes.email_regex is eml_parser.regexes.email_force_tld_regex)

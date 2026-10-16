import ipaddress

import eml_parser

raw = b"""From: a@b.com
Subject: t
Content-Type: text/plain

Please upgrade to version 999.999.999.999 today.
"""

p = eml_parser.EmlParser(include_raw_body=True)
res = p.decode_email_bytes(raw)
print('body ip field:', res['body'][0].get('ip'))

print('get_valid_domain_or_ip("999.999.999.999") ->', p.get_valid_domain_or_ip('999.999.999.999'))

raw2 = b"""From: a@b.com
Subject: t
Received: from x.com (999.999.999.999) by y.com; Mon, 1 Jan 2024 00:00:00 +0000

hi
"""
res2 = p.decode_email_bytes(raw2)
print('received_ip:', res2['header'].get('received_ip'))

import eml_parser

p = eml_parser.EmlParser(ip_force_routable=True)

for cand in ['8.8.8.8', '10.0.0.1', '127.0.0.1', '999.999.999.999', '10.0.0.256', '1.2.3.4.5']:
    print(f'{cand!r:22} -> {p.get_valid_domain_or_ip(cand)!r}')

raw = b"""From: a@b.com
Subject: t
Content-Type: text/plain

internal host 10.0.0.1 and 10.0.0.256 and 999.999.999.999
"""
print(eml_parser.EmlParser(include_raw_body=True, ip_force_routable=True).decode_email_bytes(raw)['body'][0].get('ip'))

import eml_parser

raw = (
    b'Received: by mail.example.net\r\n'
    b' for alice@example.com (qmail 21481 invoked from network);'
    b' Mon, 1 Jan 2024 10:00:00 +0100\r\n'
    b'From: bob@example.org\r\n'
    b'Subject: test\r\n'
    b'\r\n'
    b'body\r\n'
)

eml_parser.EmlParser().decode_email_bytes(raw)

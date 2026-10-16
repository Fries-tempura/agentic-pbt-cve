"""Property: decode_email_bytes is documented to apply 'some intelligence ...
in order to work around broken files' and to return a dict.  It is the single
public entry point of the library, so it should not raise on arbitrary
RFC822/MIME input.
"""

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

import eml_parser.parser

CONTENT_TYPES = [
    'text/plain',
    'text/html',
    'text/plain; charset="utf-8"',
    'text/plain; charset="bogus-charset"',
    'application/octet-stream',
    'message/rfc822',
    'message/partial',
    'message/delivery-status',
    'multipart/mixed',
    'multipart/mixed; boundary="B"',
    'multipart/alternative; boundary=""',
]

ENCODINGS = ['7bit', '8bit', 'base64', 'quoted-printable', 'x-uuencode', '']

DISPOSITIONS = ['', 'inline', 'attachment', 'attachment; filename="a.html"', 'inline; filename="x.htm"']


@st.composite
def mime_part(draw, depth=0):
    ctype = draw(st.sampled_from(CONTENT_TYPES))
    cte = draw(st.sampled_from(ENCODINGS))
    disp = draw(st.sampled_from(DISPOSITIONS))
    payload = draw(st.text(alphabet='ab \n=:-/.@<>', max_size=40))

    headers = [f'Content-Type: {ctype}']
    if cte:
        headers.append(f'Content-Transfer-Encoding: {cte}')
    if disp:
        headers.append(f'Content-Disposition: {disp}')

    if ctype.startswith('multipart') and depth < 2:
        n = draw(st.integers(min_value=0, max_value=2))
        sub = [draw(mime_part(depth + 1)) for _ in range(n)]
        body = ''.join(f'--B\n{s}\n' for s in sub) + '--B--\n'
    elif ctype == 'message/rfc822' and depth < 2:
        body = draw(mime_part(depth + 1))
    else:
        body = payload

    return '\n'.join(headers) + '\n\n' + body


@st.composite
def raw_mime_email(draw):
    top = draw(mime_part())
    extra = draw(
        st.lists(
            st.sampled_from(
                [
                    'Subject: test',
                    'From: a@b.com',
                    'To: c@d.com',
                    'Date: Mon, 1 Jan 2024 00:00:00 +0000',
                    'Date: not a date',
                    'Received: from a.com by b.com; Mon, 1 Jan 2024 00:00:00 +0000',
                    'Message-ID: <[bogus]@x.com>',
                ]
            ),
            max_size=4,
        )
    )
    return ('\n'.join(extra) + ('\n' if extra else '') + top).encode()


@settings(max_examples=2000, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(raw_mime_email())
def test_decode_email_bytes_mime(raw):
    parser = eml_parser.parser.EmlParser(include_raw_body=True, include_attachment_data=True)
    result = parser.decode_email_bytes(raw)
    assert isinstance(result, dict)


if __name__ == '__main__':
    pytest.main([__file__, '-x', '-q'])

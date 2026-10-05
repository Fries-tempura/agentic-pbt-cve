"""Property-based tests for eml_parser.parser."""

import email.message
import email.policy

import pytest
from hypothesis import given, settings, strategies as st

import eml_parser.parser


# ---------------------------------------------------------------------------
# Property 1: string_sliding_window_loop must cover the whole body.
#
# Evidence: the docstring says the function exists purely as a performance
# optimisation ("If we directly do a *regex* findall on 500K+ body we get time
# and memory issues ... in order to return a maximum possible correct URLs")
# and parse_email() feeds every slice to the URL/email/domain/IP regexes.
# Any character of the body that never appears in a yielded slice is silently
# dropped from the scan.
# ---------------------------------------------------------------------------

body_strategy = st.lists(
    st.sampled_from(list('abc ./:<>@\n') + ['https://example.com/', '://']),
    max_size=400,
).map(''.join)


@settings(max_examples=2000)
@given(body_strategy)
def test_sliding_window_covers_whole_body(body):
    covered = ''.join(eml_parser.parser.EmlParser.string_sliding_window_loop(body, slice_step=50))
    # Every character of the body must be scanned at least once.
    assert len(covered) >= len(body)
    # And the concatenation must contain the body as a subsequence of pieces:
    # cheapest sound check -> each character count must not shrink.
    for ch in set(body):
        assert covered.count(ch) >= body.count(ch), f'lost {ch!r}'


# ---------------------------------------------------------------------------
# Property 2: a URL present in the body is reported by get_uri_ondata,
# independently of how much filler text precedes it (the sliding window is an
# internal optimisation and must not change the result).
# ---------------------------------------------------------------------------

@settings(max_examples=500)
@given(
    st.integers(min_value=0, max_value=2000),
    st.sampled_from(['https://example.com/path', 'http://foo.example.org/a']),
)
def test_url_found_regardless_of_offset(pad, url):
    parser = eml_parser.parser.EmlParser()
    body = 'a' * pad + ' ' + url + ' end'
    found = parser.get_uri_ondata(body)
    assert url in found, f'pad={pad} lost url, got {found}'


# ---------------------------------------------------------------------------
# Property 3: decode_email_bytes is the library's single entry point and is
# documented to apply "some intelligence ... in order to work around broken
# files".  It should return a dict rather than raise for arbitrary RFC822-ish
# input.
# ---------------------------------------------------------------------------

header_name = st.sampled_from(
    ['Subject', 'From', 'To', 'Cc', 'Date', 'Received', 'Message-ID', 'Content-Type', 'Delivered-To']
)
header_value = st.text(
    alphabet=st.characters(blacklist_categories=('Cs',), blacklist_characters='\r\n'),
    max_size=60,
)


@st.composite
def raw_emails(draw):
    headers = draw(st.lists(st.tuples(header_name, header_value), max_size=6))
    body = draw(st.text(max_size=200))
    raw = ''.join(f'{k}: {v}\n' for k, v in headers) + '\n' + body
    return raw.encode('utf-8', 'surrogatepass')


@settings(max_examples=1000, deadline=None)
@given(raw_emails())
def test_decode_email_bytes_does_not_crash(raw):
    parser = eml_parser.parser.EmlParser(include_raw_body=True, parse_attachments=True)
    result = parser.decode_email_bytes(raw)
    assert isinstance(result, dict)
    assert 'header' in result


if __name__ == '__main__':
    pytest.main([__file__, '-x', '-q'])

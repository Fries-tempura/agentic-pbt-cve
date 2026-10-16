"""Property-based tests for eml_parser.parser that encode two claimed contracts."""

import ipaddress

import pytest
from hypothesis import given, settings, strategies as st

import eml_parser.parser
import eml_parser.regexes


# ---------------------------------------------------------------------------
# Property A
#
# parse_email() feeds every ipv4_regex / ipv6_regex match through
# get_valid_domain_or_ip() and stores whatever comes back in the output fields
# named "ip" / "received_ip".  With ip_force_routable=True the constructor
# documents: "For IP validation, requires globally routable IP."
#
# => anything get_valid_domain_or_ip() returns for an ipv4_regex match must be
#    a real IP address, and with ip_force_routable=True it must be global.
# ---------------------------------------------------------------------------

dotted_quad = st.tuples(*[st.integers(min_value=0, max_value=999)] * 4).map(lambda t: '.'.join(map(str, t)))


@settings(max_examples=1000)
@given(dotted_quad)
def test_ipv4_candidate_validated_as_ip(candidate):
    assert eml_parser.regexes.ipv4_regex.fullmatch(candidate)  # the parser would treat this as an IP

    parser = eml_parser.parser.EmlParser(ip_force_routable=True)
    result = parser.get_valid_domain_or_ip(candidate)

    if result is None:
        return

    addr = ipaddress.ip_address(result)  # must be a real IP, not a domain
    assert addr.is_global and not addr.is_reserved, f'{result} is not globally routable'


# ---------------------------------------------------------------------------
# Property B
#
# email_force_tld is documented as a per-instance option ("By default this is
# disabled").  Therefore the output of a default EmlParser must not depend on
# whether some *other* EmlParser instance was constructed first.
# ---------------------------------------------------------------------------

local_part = st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789', min_size=1, max_size=8)
no_tld_host = st.text(alphabet='abcdefghijklmnopqrstuvwxyz', min_size=1, max_size=8)


@pytest.fixture(autouse=True)
def _restore_global_regex():
    saved = eml_parser.regexes.email_regex
    yield
    eml_parser.regexes.email_regex = saved


@settings(max_examples=200, deadline=None)
@given(local_part, no_tld_host)
def test_email_force_tld_is_per_instance(local, host):
    eml_parser.regexes.email_regex = eml_parser.regexes.email_regex  # noqa: PLW0127 (explicit: start from current state)
    saved = eml_parser.regexes.email_regex
    try:
        raw = f'From: a@b.com\nSubject: t\nContent-Type: text/plain\n\ncontact {local}@{host} here\n'.encode()

        parser = eml_parser.parser.EmlParser(include_raw_body=True)
        before = parser.decode_email_bytes(raw)['body'][0].get('email')

        eml_parser.parser.EmlParser(email_force_tld=True)  # unrelated instance

        after = parser.decode_email_bytes(raw)['body'][0].get('email')

        assert before == after, f'default parser changed behaviour: {before} -> {after}'
    finally:
        eml_parser.regexes.email_regex = saved


if __name__ == '__main__':
    pytest.main([__file__, '-q'])

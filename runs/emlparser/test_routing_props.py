"""Property-based tests for eml_parser.routing."""

import eml_parser.routing as routing
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Strategy: realistic "Received:" header lines.
#
# eml_parser.parser feeds parserouting() with the flattened (whitespace
# collapsed) content of a Received header, see parser.py:341-354.  Real
# Received lines are built from the RFC 5321 clauses from/by/with/for, host
# names / IPs, optional CFWS comments in parentheses and a trailing "; date".
# ---------------------------------------------------------------------------

HOSTS = st.sampled_from(
    [
        'mail.example.com',
        'smtp.example.org',
        '10.0.0.1',
        '[192.168.1.2]',
        'localhost',
        'mx1.gov.lu',
    ]
)

ADDRS = st.sampled_from(['alice@example.com', 'bob@example.org', '<carol@example.net>'])

DATES = st.sampled_from(
    [
        '; Mon, 1 Jan 2024 10:00:00 +0100',
        '; Tue, 2 Feb 2021 23:59:59 -0500 (CET)',
        '',
    ]
)

COMMENTS = st.sampled_from(
    [
        '(helo=mail.example.com)',
        '(mail.example.com [10.0.0.1])',
        '(from userid 500)',
        '(qmail 21481 invoked from network)',
        '(user bob authenticated from 10.0.0.1)',
        '(envelope-from alice@example.com)',
        '',
    ]
)


@st.composite
def received_lines(draw: st.DrawFn) -> str:
    parts: list[str] = []

    if draw(st.booleans()):
        parts.append('from ' + draw(HOSTS))
        parts.append(draw(COMMENTS))
    if draw(st.booleans()):
        parts.append('by ' + draw(HOSTS))
        parts.append(draw(COMMENTS))
    if draw(st.booleans()):
        parts.append('with ' + draw(st.sampled_from(['ESMTP', 'ESMTPS id ABC123', 'SMTP'])))
    if draw(st.booleans()):
        parts.append('for ' + draw(ADDRS))
        parts.append(draw(COMMENTS))

    line = ' '.join(p for p in parts if p) + draw(DATES)
    return ' '.join(line.split())


# ---------------------------------------------------------------------------
# Property 1: parserouting() is the single entry point of this module and is
# documented as "we try our best to match a large number of formats" and to
# "return a dict with the extracted information" -- it must not raise on
# arbitrary Received-header content.  parser.py only guards it with
# `except TypeError` (parser.py:410), so anything else escapes to the caller.
# ---------------------------------------------------------------------------
@settings(max_examples=2000)
@given(received_lines())
def test_parserouting_never_crashes(line: str) -> None:
    out = routing.parserouting(line)
    assert isinstance(out, dict)
    assert out['src'] == line


# ---------------------------------------------------------------------------
# Property 2: cleanline() -- "Remove space and ; from start/end of line."
# ---------------------------------------------------------------------------
@given(st.text())
def test_cleanline_strips_borders(line: str) -> None:
    result = routing.cleanline(line)
    assert result == result.strip(' ;\t\r\n\v\f')


@given(st.text())
def test_cleanline_idempotent(line: str) -> None:
    once = routing.cleanline(line)
    assert routing.cleanline(once) == once


# ---------------------------------------------------------------------------
# Property 3: noparenthesis() -- "Remove nested parenthesis, until none are
# present." -> running it again must be a no-op (fixed point).
# ---------------------------------------------------------------------------
@given(st.text(alphabet=st.sampled_from('()ab '), max_size=40))
def test_noparenthesis_idempotent(line: str) -> None:
    once = routing.noparenthesis(line)
    assert routing.noparenthesis(once) == once


# ---------------------------------------------------------------------------
# Property 4: get_domain_ip() -- "Unique list of strings with matches".
# ---------------------------------------------------------------------------
@given(st.text())
def test_get_domain_ip_unique(line: str) -> None:
    result = routing.get_domain_ip(line)
    assert isinstance(result, list)
    assert len(result) == len(set(result))
    assert all(isinstance(x, str) for x in result)

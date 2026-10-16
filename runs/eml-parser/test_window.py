"""Properties of EmlParser.string_sliding_window_loop.

The docstring states the slicing exists only because "If we directly do a
*regex* findall on 500K+ body we get time and memory issues", i.e. it is a
pure performance optimisation, and that the rewinding logic is there "in order
to return a maximum possible correct URLs".

Two consequences the code claims:
  P1 - coverage: every character of the body ends up in at least one slice
       (otherwise URLs/e-mails/domains/IPs in that region are silently lost).
  P2 - equivalence: scanning the slices yields the same URLs as scanning the
       whole body at once.
"""

import pytest
from hypothesis import given, settings, strategies as st

import eml_parser.parser

URL = 'https://example.com/aaaa'


def window_ranges(body, slice_step=500, max_distance=100):
    """Index-tracking clone of EmlParser.string_sliding_window_loop."""
    import eml_parser.regexes

    body_length = len(body)
    out = []

    if body_length <= slice_step:
        out.append((0, body_length))
        return out

    ptr_start = 0
    for ptr_end in range(slice_step, body_length + slice_step, slice_step):
        if ' ' in body[ptr_end - 1 : ptr_end]:
            while not (eml_parser.regexes.window_slice_regex.match(body[ptr_end - 1 : ptr_end]) or ptr_end > body_length):
                if ptr_end > body_length:
                    ptr_end = body_length
                    break
                ptr_end += 1

        if ptr_start > 16 and '://' in body[ptr_start - 8 : ptr_start + 8]:
            ptr_start -= 16

        if ptr_end < body_length and '://' in body[ptr_end - 8 : ptr_end + 8]:
            pos = body.rfind('://', ptr_end - 8, ptr_end + 8)
            ptr_end = pos - 8

        if '://' in body[ptr_start:ptr_end] and not body[ptr_end - 1 : ptr_end] == ' ':
            distance = 1
            while body[ptr_end - 1 : ptr_end] not in (' ', '>') and distance < max_distance and ptr_end <= body_length:
                distance += 1
                ptr_end += 1

        out.append((ptr_start, ptr_end))
        ptr_start = ptr_end

    return out


@st.composite
def bodies(draw):
    chunks = draw(
        st.lists(
            st.one_of(
                st.text(alphabet='ab ', min_size=1, max_size=120),
                st.just(URL),
                st.just('http://foo.example.org/path'),
            ),
            min_size=1,
            max_size=60,
        )
    )
    return ' '.join(chunks)


@settings(max_examples=2000, deadline=None)
@given(bodies())
def test_window_ranges_match_implementation(body):
    """Sanity: the index-tracking clone reproduces the real generator."""
    real = list(eml_parser.parser.EmlParser.string_sliding_window_loop(body))
    clone = [body[a:b] for a, b in window_ranges(body)]
    assert real == clone


@settings(max_examples=2000, deadline=None)
@given(bodies())
def test_window_covers_every_character(body):
    """P1: no character of the body may be skipped by the slicing."""
    covered = set()
    for a, b in window_ranges(body):
        covered.update(range(max(a, 0), max(b, 0)))
    missing = sorted(set(range(len(body))) - covered)
    assert not missing, f'uncovered indices {missing[:20]} (len={len(body)})'


@settings(max_examples=2000, deadline=None)
@given(bodies())
def test_sliced_scan_equals_whole_scan(body):
    """P2: slicing must not change which URLs are found."""
    parser = eml_parser.parser.EmlParser()
    whole = set(parser.get_uri_ondata(body))
    sliced = set()
    for part in eml_parser.parser.EmlParser.string_sliding_window_loop(body):
        sliced.update(parser.get_uri_ondata(part))
    assert whole == sliced, f'whole-sliced={whole - sliced}, sliced-whole={sliced - whole}'


if __name__ == '__main__':
    pytest.main([__file__, '-q'])

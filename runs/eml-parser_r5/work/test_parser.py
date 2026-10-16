import re
from hypothesis import given, settings, strategies as st, assume
from eml_parser.parser import EmlParser

hname = st.sampled_from(['Subject', 'From', 'To', 'X-Foo'])
hval = st.text(st.characters(min_codepoint=0x21, max_codepoint=0x7e, blacklist_characters=':'), min_size=1, max_size=20)

def strip_volatile(r):
    for b in r.get('body', []):
        pass
    return r

@settings(max_examples=200)
@given(st.lists(st.tuples(hname, hval), min_size=1, max_size=5), st.text(st.characters(min_codepoint=0x20, max_codepoint=0x7e), max_size=50))
def test_ignore_bad_start_noop_on_valid(headers, body):
    raw = ''.join(f'{k}: {v}\n' for k, v in headers) + '\n' + body + '\n'
    p = EmlParser(include_raw_body=True)
    a = p.decode_email_bytes(raw.encode())
    b = p.decode_email_bytes(raw.encode(), ignore_bad_start=True)
    assert a['header']['header'] == b['header']['header']
    assert [x['content'] for x in a['body']] == [x['content'] for x in b['body']]

url_chars = st.text('abcdefghij', min_size=1, max_size=10)
@settings(max_examples=500)
@given(st.lists(st.one_of(st.text(' abcxyz\n.', min_size=0, max_size=60),
                          st.builds(lambda h, p: f' http://{h}.com/{p} ', url_chars, url_chars)), max_size=60))
def test_sliding_window_finds_urls(parts):
    body = ''.join(parts)
    p = EmlParser()
    full = set(p.get_uri_ondata(body))
    sliced = set()
    for s in EmlParser.string_sliding_window_loop(body):
        sliced |= set(p.get_uri_ondata(s))
    assert full <= sliced, full - sliced

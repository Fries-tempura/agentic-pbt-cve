import pytest
from hypothesis import given, settings, strategies as st, assume
from h11._readers import ChunkedReader, ContentLengthReader
from h11._receivebuffer import ReceiveBuffer
from h11._events import Data, EndOfMessage
from h11._util import LocalProtocolError

def encode_chunked(chunks):
    out = b""
    for c in chunks:
        out += b"%x\r\n" % len(c) + c + b"\r\n"
    return out + b"0\r\n\r\n"

def feed_all(reader, pieces):
    buf = ReceiveBuffer()
    events = []
    for p in pieces:
        buf += p
        while True:
            ev = reader(buf)
            if ev is None:
                break
            events.append(ev)
            if isinstance(ev, EndOfMessage):
                return events
    return events

def split(data, cuts):
    cuts = sorted(set(c % (len(data) + 1) for c in cuts))
    pieces, prev = [], 0
    for c in cuts:
        pieces.append(data[prev:c]); prev = c
    pieces.append(data[prev:])
    return pieces

chunks_st = st.lists(st.binary(min_size=1), max_size=6)

@given(chunks_st, st.lists(st.integers(min_value=0)))
@settings(max_examples=500)
def test_chunked_roundtrip_any_split(chunks, cuts):
    wire = encode_chunked(chunks)
    events = feed_all(ChunkedReader(), split(wire, cuts))
    assert isinstance(events[-1], EndOfMessage)
    assert b"".join(e.data for e in events if isinstance(e, Data)) == b"".join(chunks)

@given(chunks_st, st.binary(min_size=2, max_size=2).filter(lambda b: b != b"\r\n"))
@settings(max_examples=300)
def test_chunked_rejects_bad_chunk_terminator(chunks, bad):
    assume(chunks)
    wire = b""
    for c in chunks:
        wire += b"%x\r\n" % len(c) + c + bad
    wire += b"0\r\n\r\n"
    with pytest.raises(LocalProtocolError):
        feed_all(ChunkedReader(), [wire])

@given(st.binary(), st.lists(st.integers(min_value=0)))
def test_content_length_roundtrip(body, cuts):
    events = feed_all(ContentLengthReader(len(body)), split(body, cuts) + [b""])
    assert isinstance(events[-1], EndOfMessage)
    assert b"".join(e.data for e in events if isinstance(e, Data)) == body

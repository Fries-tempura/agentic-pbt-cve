import pytest
from hypothesis import given, settings, strategies as st
from h11._readers import ChunkedReader, ContentLengthReader, maybe_read_from_IDLE_client
from h11._receivebuffer import ReceiveBuffer
from h11._events import Data, EndOfMessage
from h11._util import LocalProtocolError, RemoteProtocolError


def drive(reader, pieces):
    buf = ReceiveBuffer()
    events = []
    for i, p in enumerate(pieces):
        buf += p
        while True:
            ev = reader(buf)
            if ev is None:
                break
            events.append(ev)
            if isinstance(ev, EndOfMessage):
                return events, bytes(buf) + b"".join(pieces[i + 1:])
    return events, bytes(buf)


def split(data, cuts):
    cuts = sorted(set(c % (len(data) + 1) for c in cuts))
    out, prev = [], 0
    for c in cuts + [len(data)]:
        out.append(data[prev:c]); prev = c
    return out


def encode_chunked(chunks):
    out = b""
    for c in chunks:
        out += b"%x\r\n" % len(c) + c + b"\r\n"
    return out + b"0\r\n\r\n"


chunks_st = st.lists(st.binary(min_size=1, max_size=50), max_size=8)


@settings(max_examples=500)
@given(chunks_st, st.lists(st.integers(0, 10**6), max_size=10), st.binary(max_size=20))
def test_chunked_roundtrip_any_split(chunks, cuts, trailing):
    wire = encode_chunked(chunks)
    events, rest = drive(ChunkedReader(), split(wire + trailing, cuts))
    assert isinstance(events[-1], EndOfMessage)
    assert b"".join(bytes(e.data) for e in events[:-1]) == b"".join(chunks)
    assert rest == trailing


@settings(max_examples=500)
@given(st.binary(min_size=1, max_size=50), st.binary(min_size=2, max_size=2).filter(lambda b: b != b"\r\n"))
def test_chunked_rejects_bad_chunk_terminator(chunk, bad):
    wire = b"%x\r\n" % len(chunk) + chunk + bad + b"0\r\n\r\n"
    with pytest.raises((LocalProtocolError, RemoteProtocolError)):
        drive(ChunkedReader(), [wire])


@settings(max_examples=300)
@given(st.binary(max_size=200), st.integers(0, 200), st.lists(st.integers(0, 10**6), max_size=10))
def test_content_length_reader(data, n, cuts):
    events, rest = drive(ContentLengthReader(n), split(data, cuts) + [b""])
    body = b"".join(bytes(e.data) for e in events if isinstance(e, Data))
    if len(data) >= n:
        assert isinstance(events[-1], EndOfMessage)
        assert body == data[:n] and rest == data[n:]
    else:
        assert body == data

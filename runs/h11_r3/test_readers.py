import pytest
from hypothesis import given, settings, strategies as st
from h11._readers import ChunkedReader, ContentLengthReader
from h11._receivebuffer import ReceiveBuffer
from h11._events import Data, EndOfMessage
from h11._util import LocalProtocolError, RemoteProtocolError


def drive(reader, pieces):
    buf = ReceiveBuffer()
    out = []
    for i, p in enumerate(pieces):
        buf += p
        while True:
            ev = reader(buf)
            if ev is None:
                break
            out.append(ev)
            if isinstance(ev, EndOfMessage):
                return out, bytes(buf) + b"".join(pieces[i + 1:])
    return out, bytes(buf)


def split(data, cuts):
    cuts = sorted({c % (len(data) + 1) for c in cuts})
    pieces, prev = [], 0
    for c in cuts + [len(data)]:
        pieces.append(data[prev:c]); prev = c
    return pieces


chunks_st = st.lists(st.binary(min_size=1, max_size=50), max_size=8)


@given(chunks_st, st.lists(st.integers(0, 10**6)), st.binary(max_size=20))
@settings(max_examples=500)
def test_chunked_roundtrip(chunks, cuts, trailing):
    wire = b"".join(b"%x\r\n" % len(c) + c + b"\r\n" for c in chunks) + b"0\r\n\r\n"
    out, rest = drive(ChunkedReader(), split(wire + trailing, cuts))
    assert isinstance(out[-1], EndOfMessage)
    assert b"".join(e.data for e in out if isinstance(e, Data)) == b"".join(chunks)
    assert rest == trailing


@given(st.binary(min_size=1, max_size=50),
       st.binary(min_size=2, max_size=2).filter(lambda t: t != b"\r\n"))
@settings(max_examples=300)
def test_chunked_rejects_bad_chunk_terminator(chunk, term):
    wire = b"%x\r\n" % len(chunk) + chunk + term + b"0\r\n\r\n"
    with pytest.raises(LocalProtocolError):
        drive(ChunkedReader(), [wire])


@given(st.binary(max_size=100), st.lists(st.integers(0, 10**6)), st.binary(max_size=20))
def test_content_length_roundtrip(body, cuts, trailing):
    out, rest = drive(ContentLengthReader(len(body)), split(body + trailing, cuts))
    assert isinstance(out[-1], EndOfMessage)
    assert b"".join(e.data for e in out if isinstance(e, Data)) == body
    assert rest == trailing

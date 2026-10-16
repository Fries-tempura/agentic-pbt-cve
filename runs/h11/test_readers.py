from hypothesis import given, settings, strategies as st, assume
import pytest

from h11._readers import ChunkedReader, ContentLengthReader
from h11._receivebuffer import ReceiveBuffer
from h11._events import Data, EndOfMessage
from h11._util import LocalProtocolError, RemoteProtocolError
import h11


def encode_chunked(chunks):
    out = b""
    for c in chunks:
        out += b"%x\r\n" % len(c) + c + b"\r\n"
    return out + b"0\r\n\r\n"


def run_reader(reader, pieces):
    buf = ReceiveBuffer()
    data = b""
    for k, p in enumerate(pieces):
        buf += p
        while True:
            ev = reader(buf)
            if ev is None:
                break
            if isinstance(ev, EndOfMessage):
                return data, True, bytes(buf) + b"".join(pieces[k + 1:])
            data += ev.data
    return data, False, bytes(buf)


def split(raw, cuts):
    cuts = sorted(set(c % (len(raw) + 1) for c in cuts))
    pieces, prev = [], 0
    for c in cuts + [len(raw)]:
        pieces.append(raw[prev:c])
        prev = c
    return pieces


chunks_st = st.lists(st.binary(min_size=1, max_size=50), max_size=8)


@settings(max_examples=500)
@given(chunks_st, st.lists(st.integers(min_value=0, max_value=10_000)))
def test_chunked_roundtrip_any_split(chunks, cuts):
    raw = encode_chunked(chunks)
    data, done, rest = run_reader(ChunkedReader(), split(raw, cuts))
    assert done
    assert data == b"".join(chunks)
    assert rest == b""


@settings(max_examples=500)
@given(st.binary(max_size=200), st.lists(st.integers(min_value=0, max_value=1000)),
       st.binary(max_size=20))
def test_content_length_roundtrip(body, cuts, extra):
    raw = body + extra
    data, done, rest = run_reader(ContentLengthReader(len(body)), split(raw, cuts))
    assert done
    assert data == body
    assert rest == extra


@settings(max_examples=500)
@given(chunks_st.filter(lambda c: len(c) > 0), st.data(),
       st.binary(min_size=2, max_size=2).filter(lambda b: b != b"\r\n"))
def test_chunked_rejects_bad_chunk_terminator(chunks, data, bad):
    i = data.draw(st.integers(0, len(chunks) - 1))
    raw = b""
    for j, c in enumerate(chunks):
        raw += b"%x\r\n" % len(c) + c + (bad if j == i else b"\r\n")
    raw += b"0\r\n\r\n"
    with pytest.raises((LocalProtocolError, RemoteProtocolError)):
        run_reader(ChunkedReader(), [raw])

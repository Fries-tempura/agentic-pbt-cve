import pytest
from hypothesis import given, settings, assume, strategies as st
from h11._readers import ChunkedReader, ContentLengthReader
from h11._receivebuffer import ReceiveBuffer
from h11._writers import ChunkedWriter
from h11._events import Data, EndOfMessage
from h11._util import LocalProtocolError
import h11
from h11._headers import normalize_and_validate


def drive(reader, pieces):
    buf = ReceiveBuffer()
    out, eom = b"", None
    for i, p in enumerate(pieces):
        buf += p
        while True:
            ev = reader(buf)
            if ev is None:
                break
            if isinstance(ev, EndOfMessage):
                return out, ev, bytes(buf) + b"".join(pieces[i + 1:])
            out += bytes(ev.data)
    return out, None, bytes(buf)


def split(data, cuts):
    cuts = sorted(set(c % (len(data) + 1) for c in cuts))
    pts = [0] + cuts + [len(data)]
    return [data[a:b] for a, b in zip(pts, pts[1:])]


@settings(max_examples=500)
@given(st.lists(st.binary()), st.lists(st.integers(min_value=0)))
def test_chunked_roundtrip(chunks, cuts):
    w = ChunkedWriter()
    parts = []
    for c in chunks:
        w.send_data(c, parts.append)
    w.send_eom(normalize_and_validate([]), parts.append)
    wire = b"".join(parts)
    out, eom, rest = drive(ChunkedReader(), split(wire, cuts))
    assert eom is not None
    assert out == b"".join(chunks)
    assert rest == b""


@settings(max_examples=500)
@given(st.binary(min_size=1), st.binary(min_size=2, max_size=2))
def test_chunk_terminator_must_be_crlf(data, term):
    assume(term != b"\r\n")
    wire = b"%x\r\n" % len(data) + data + term + b"0\r\n\r\n"
    with pytest.raises(h11.RemoteProtocolError):
        conn = h11.Connection(h11.SERVER)
        conn.receive_data(
            b"POST / HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: chunked\r\n\r\n" + wire
        )
        while True:
            ev = conn.next_event()
            if ev in (h11.NEED_DATA, h11.PAUSED):
                break


@settings(max_examples=500)
@given(st.binary(), st.binary(), st.lists(st.integers(min_value=0)))
def test_content_length(body, extra, cuts):
    out, eom, rest = drive(ContentLengthReader(len(body)), split(body + extra, cuts))
    assert eom is not None
    assert out == body
    assert rest == extra

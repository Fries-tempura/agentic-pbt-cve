# Bug Report: h11._readers ChunkedReader accepts arbitrary bytes instead of chunk-terminating CRLF

**Target**: `h11._readers.ChunkedReader`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

After reading a chunk's data, `ChunkedReader` blindly discards the next 2 bytes, assuming they are `\r\n` (as its own comment states: "we have to throw away the trailing \r\n"). It never verifies them, so malformed chunked bodies like `5\r\nAAAAAXX0\r\n\r\n` are silently accepted. Because other HTTP implementations parse such bodies differently, this enables HTTP request smuggling (this is CVE-2025-43859).

## Property-Based Test

```python
import pytest
from hypothesis import given, settings, strategies as st, assume
from h11._readers import ChunkedReader
from h11._receivebuffer import ReceiveBuffer
from h11._events import EndOfMessage
from h11._util import LocalProtocolError

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

chunks_st = st.lists(st.binary(min_size=1), max_size=6)

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
```

**Failing input**: `chunks=[b'\x00'], bad=b'\x00\x00'` (fails for every generated value)

## Reproducing the Bug

```python
import h11

conn = h11.Connection(h11.SERVER)
conn.receive_data(
    b"POST / HTTP/1.1\r\nHost: example.com\r\nTransfer-Encoding: chunked\r\n\r\n"
    b"5\r\nAAAAAXX"
    b"0\r\n\r\n"
)
print(conn.next_event())  # Request(...)
print(conn.next_event())  # Data(data=b'AAAAA', ...)
print(conn.next_event())  # EndOfMessage()  -- should have raised RemoteProtocolError
```

## Why This Is A Bug

RFC 9112 §7.1 requires every `chunk-data` to be followed by CRLF. The code's own comment states the 2 discarded bytes are the trailing `\r\n`, but they are never checked. Accepting arbitrary bytes there means h11 and a front-end proxy can disagree about where a message ends, which is a classic request-smuggling primitive (e.g. a proxy that treats `XX` as part of the stream / line-based parsing sees a different request boundary than h11).

## Fix

```diff
--- a/h11/_readers.py
+++ b/h11/_readers.py
@@ class ChunkedReader:
         if self._bytes_to_discard > 0:
             data = buf.maybe_extract_at_most(self._bytes_to_discard)
             if data is None:
                 return None
+            expected = b"\r\n"[2 - self._bytes_to_discard :][: len(data)]
+            if data != expected:
+                raise LocalProtocolError(
+                    "malformed chunk footer: {!r} (expected {!r})".format(data, expected)
+                )
             self._bytes_to_discard -= len(data)
             if self._bytes_to_discard > 0:
                 return None
```

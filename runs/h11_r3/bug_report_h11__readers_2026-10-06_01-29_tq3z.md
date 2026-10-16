# Bug Report: h11._readers.ChunkedReader accepts arbitrary bytes as chunk terminator

**Target**: `h11._readers.ChunkedReader`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

After reading a chunk's data, `ChunkedReader` discards the next 2 bytes without checking that they are `\r\n`. Any 2 bytes are accepted as the chunk terminator. This is a parsing discrepancy that can enable HTTP request smuggling (CVE-2025-43859).

## Property-Based Test

```python
import pytest
from hypothesis import given, settings, strategies as st
from h11._readers import ChunkedReader
from h11._receivebuffer import ReceiveBuffer
from h11._events import EndOfMessage
from h11._util import LocalProtocolError


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


@given(st.binary(min_size=1, max_size=50),
       st.binary(min_size=2, max_size=2).filter(lambda t: t != b"\r\n"))
@settings(max_examples=300)
def test_chunked_rejects_bad_chunk_terminator(chunk, term):
    wire = b"%x\r\n" % len(chunk) + chunk + term + b"0\r\n\r\n"
    with pytest.raises(LocalProtocolError):
        drive(ChunkedReader(), [wire])
```

**Failing input**: `chunk=b'\x00', term=b'\x00\x00'`

## Reproducing the Bug

```python
import h11

conn = h11.Connection(h11.SERVER)
conn.receive_data(
    b"POST / HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: chunked\r\n\r\n"
    b"5\r\nAAAAAXX"
    b"0\r\n\r\n"
)
while True:
    ev = conn.next_event()
    print(ev)
    if ev is h11.NEED_DATA or type(ev) is h11.EndOfMessage:
        break
```

Output: `Request(...)`, `Data(data=b'AAAAA', ...)`, `EndOfMessage(...)`. The invalid `XX` terminator is silently accepted.

## Why This Is A Bug

RFC 9112 §7.1 requires every chunk's data to be followed by CRLF (`chunk = chunk-size [ chunk-ext ] CRLF chunk-data CRLF`). The reader's own comment says it throws away "the trailing \r\n", but it never checks that those bytes are actually `\r\n`. A front-end proxy that frames the stream differently (for example, one that treats the bytes after a short chunk as part of the next chunk-size line) will disagree with h11 about where a message ends. An attacker can use that disagreement to smuggle a request into the next message on a keep-alive connection. This is the issue behind CVE-2025-43859.

## Fix

```diff
--- a/h11/_readers.py
+++ b/h11/_readers.py
@@ class ChunkedReader:
         if self._bytes_to_discard > 0:
             data = buf.maybe_extract_at_most(self._bytes_to_discard)
             if data is None:
                 return None
+            if data != b"\r\n"[2 - self._bytes_to_discard :][: len(data)]:
+                raise LocalProtocolError(
+                    "malformed chunk footer: {!r} (expected b'\\r\\n')".format(data)
+                )
             self._bytes_to_discard -= len(data)
             if self._bytes_to_discard > 0:
                 return None
```

(Upstream h11 0.16.0 fixes this by storing the expected remaining bytes, e.g. `self._bytes_to_discard = b"\r\n"`, and comparing each extracted piece against its prefix.)

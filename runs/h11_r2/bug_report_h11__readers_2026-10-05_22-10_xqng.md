# Bug Report: h11._readers ChunkedReader accepts arbitrary bytes instead of CRLF after chunk data

**Target**: `h11._readers.ChunkedReader`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

After reading a chunk's data, `ChunkedReader` throws away the next 2 bytes without checking them. Its comment says these are "the trailing \r\n", but any 2 bytes are accepted, so malformed chunked bodies get through. Because h11 and other HTTP parsers disagree on where the message ends, this allows HTTP request smuggling (the issue tracked as CVE-2025-43859).

## Property-Based Test

```python
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
```

**Failing input**: `data=b'\x00', term=b'\x00\x00'`

## Reproducing the Bug

```python
import h11

conn = h11.Connection(h11.SERVER)
conn.receive_data(
    b"POST / HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: chunked\r\n\r\n"
    b"1\r\nAXX0\r\n\r\n"
)
while (ev := conn.next_event()) not in (h11.NEED_DATA, h11.PAUSED):
    print(ev)
# Request(...), Data(data=bytearray(b'A'), ...), EndOfMessage(...)  -- no error
```

## Why This Is A Bug

RFC 9112 §7.1 defines `chunk = chunk-size [ chunk-ext ] CRLF chunk-data CRLF`. The code's own comment says the bytes it discards are "the trailing \r\n", and h11 is strict about the chunk header line. Even so, `1\r\nAXX0\r\n\r\n` is accepted as a valid body: `XX` is silently dropped. A front-end proxy that frames the stream differently (for example, one that treats the extra bytes as part of the chunk or as the start of the next line) will disagree with h11 about where a request ends. An attacker can use that disagreement to smuggle requests.

## Fix

```diff
--- a/h11/_readers.py
+++ b/h11/_readers.py
@@ class ChunkedReader:
     def __init__(self) -> None:
         self._bytes_in_chunk = 0
-        # After reading a chunk, we have to throw away the trailing \r\n; if
-        # this is >0 then we discard that many bytes before resuming regular
-        # de-chunkification.
-        self._bytes_to_discard = 0
+        # After reading a chunk, we have to throw away the trailing \r\n.
+        # This tracks the bytes that we need to match and throw away.
+        self._bytes_to_discard = b""
         self._reading_trailer = False
@@
-        if self._bytes_to_discard > 0:
-            data = buf.maybe_extract_at_most(self._bytes_to_discard)
+        if self._bytes_to_discard:
+            data = buf.maybe_extract_at_most(len(self._bytes_to_discard))
             if data is None:
                 return None
-            self._bytes_to_discard -= len(data)
-            if self._bytes_to_discard > 0:
+            if data != self._bytes_to_discard[: len(data)]:
+                raise LocalProtocolError(
+                    f"malformed chunk footer: {data!r} (expected {self._bytes_to_discard!r})"
+                )
+            self._bytes_to_discard = self._bytes_to_discard[len(data) :]
+            if self._bytes_to_discard:
                 return None
             # else, fall through and read some more
-        assert self._bytes_to_discard == 0
+        assert self._bytes_to_discard == b""
@@
         if self._bytes_in_chunk == 0:
-            self._bytes_to_discard = 2
+            self._bytes_to_discard = b"\r\n"
             chunk_end = True
```

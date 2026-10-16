# Bug Report: h11._readers.ChunkedReader accepts any 2 bytes as chunk terminator

**Target**: `h11._readers.ChunkedReader`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

After each chunk's data, `ChunkedReader` throws away the next 2 bytes without checking that they are `\r\n`. As a result, malformed chunked bodies are accepted silently. Proxies and servers that frame the same bytes differently can disagree on where the message ends, which enables HTTP request smuggling (CVE-2025-43859).

## Property-Based Test

```python
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
```

**Failing input**: `chunks=[b'\x00'], bad=b'\x00\x00'` (it fails for every generated value)

## Reproducing the Bug

```python
import h11

conn = h11.Connection(h11.SERVER)
conn.receive_data(
    b"POST / HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n"
    b"1\r\nAXX0\r\n\r\n"
)
while True:
    ev = conn.next_event()
    print(ev)
    if ev is h11.NEED_DATA or isinstance(ev, h11.EndOfMessage):
        break
```

Output: `Request(...)`, `Data(data=bytearray(b'A'), ...)`, `EndOfMessage(...)`. The malformed body is accepted with no error.

## Why This Is A Bug

RFC 9112 §7.1 defines `chunk = chunk-size [chunk-ext] CRLF chunk-data CRLF`. The code's own comment says these bytes are "the trailing \r\n", but it never checks them. Every other framing error in h11 (bad chunk header, bad header line) raises `LocalProtocolError`, so this one should too. Other parsers handle the same input differently: some reject it, and some treat the bytes as part of the data. That disagreement is the request-smuggling primitive behind CVE-2025-43859.

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
+        # After reading a chunk, we have to throw away the trailing \r\n.
+        # This tracks the bytes that we need to match and throw away.
-        self._bytes_to_discard = 0
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

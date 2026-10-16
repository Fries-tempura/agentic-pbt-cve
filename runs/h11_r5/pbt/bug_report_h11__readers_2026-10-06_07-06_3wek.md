# Bug Report: h11._readers ChunkedReader accepts any 2 bytes as the chunk-data terminator

**Target**: `h11._readers.ChunkedReader`
**Severity**: High
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

After reading a chunk's data, `ChunkedReader` silently discards the next 2 bytes without checking that they are `\r\n`. Malformed chunked bodies are therefore accepted. Since other HTTP implementations frame these bodies differently, this enables HTTP request smuggling (this is CVE-2025-43859).

## Property-Based Test

```python
@settings(max_examples=500)
@given(st.binary(min_size=1, max_size=50), st.binary(min_size=2, max_size=2).filter(lambda b: b != b"\r\n"))
def test_chunked_rejects_bad_chunk_terminator(chunk, bad):
    wire = b"%x\r\n" % len(chunk) + chunk + bad + b"0\r\n\r\n"
    with pytest.raises((LocalProtocolError, RemoteProtocolError)):
        drive(ChunkedReader(), [wire])
```

**Failing input**: `chunk=b'\x00', bad=b'\x00\x00'`

## Reproducing the Bug

```python
import h11

conn = h11.Connection(h11.SERVER)
conn.receive_data(
    b"POST / HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: chunked\r\n\r\n"
    b"5\r\nAAAAAXX"
    b"0\r\n\r\n"
)
print(conn.next_event())
print(conn.next_event())
print(conn.next_event())
```

Output: `Request(...)`, `Data(data=bytearray(b'AAAAA'), ...)`, `EndOfMessage(...)`. The bytes `XX` sit where the mandatory CRLF should be, yet the body is accepted.

## Why This Is A Bug

RFC 9112 §7.1 defines `chunk = chunk-size [ chunk-ext ] CRLF chunk-data CRLF`. The code's own comment says "we have to throw away the trailing \r\n", but it never checks those bytes. Everywhere else h11 rejects malformed framing (chunk headers and header lines go through `validate`). A front-end proxy that frames the same bytes differently (for example, one that treats a bare `\n` as the line terminator or reads past the declared size) disagrees with h11 about where the message ends. That disagreement lets an attacker smuggle a request.

## Fix

```diff
--- a/h11/_readers.py
+++ b/h11/_readers.py
@@ class ChunkedReader:
         if self._bytes_to_discard > 0:
-            data = buf.maybe_extract_at_most(self._bytes_to_discard)
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
+        assert not self._bytes_to_discard
@@
         if self._bytes_in_chunk == 0:
-            self._bytes_to_discard = 2
+            self._bytes_to_discard = b"\r\n"
```
(`__init__` also needs `self._bytes_to_discard = b""` and the `> 0` check changed to a truthiness check.) This matches the upstream fix in h11 0.16.0.

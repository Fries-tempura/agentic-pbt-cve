import inspect, h11._readers as r
src = inspect.getsource(r.ChunkedReader).replace(
"""            if data is None:
                return None
            self._bytes_to_discard -= len(data)""",
"""            if data is None:
                return None
            expected = b"\\r\\n"[2 - self._bytes_to_discard :][: len(data)]
            if data != expected:
                raise LocalProtocolError("malformed chunk footer")
            self._bytes_to_discard -= len(data)""")
exec(src, r.__dict__)

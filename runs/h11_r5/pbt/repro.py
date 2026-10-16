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
    if ev in (h11.NEED_DATA, h11.PAUSED) or isinstance(ev, h11.EndOfMessage):
        break

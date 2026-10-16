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

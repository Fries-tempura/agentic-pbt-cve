import h11

conn = h11.Connection(h11.SERVER)
conn.receive_data(
    b"POST / HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: chunked\r\n\r\n"
    b"1\r\nAXX0\r\n\r\n"
)
while (ev := conn.next_event()) not in (h11.NEED_DATA, h11.PAUSED):
    print(ev)

conn = h11.Connection(h11.SERVER)
conn.receive_data(
    b"GET /one HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\n\r\n"
    b"5\r\nAAAAAXX2\r\n45\r\n0\r\n\r\n"
    b"GET /two HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n"
)
while (ev := conn.next_event()) not in (h11.NEED_DATA, h11.PAUSED):
    print(ev)

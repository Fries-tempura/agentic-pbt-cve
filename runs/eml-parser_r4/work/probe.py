import time, eml_parser.parser as P
ep = P.EmlParser(include_raw_body=True)
cases = {
 "www_dots": " www." + "a."*3000 + "!",
 "www_word": " www." + "a"*3000 + "!",
 "href": "<a " + "href"*3000,
 "img": "<img " + " "*5000,
 "url": "http://" + "a"*5000 + "!",
 "email": "a"*5000 + "@",
 "dom": " " + "a."*5000,
 "ipv6": "1:"*5000,
 "rfc2047hdr": None,
}
for name, b in cases.items():
    if b is None: continue
    for n in (1, 2, 4):
        body = b * n
        msg = ("From: a@b.com\nSubject: s\n\n" + body).encode()
        t = time.time(); ep.decode_email_bytes(msg); dt = time.time() - t
        print(name, len(body), round(dt, 3))
# header side
for name, h in {"received": "Received: " + "from a "*3000, "subj": "Subject: " + "=?utf-8?b?" * 3000, "from": "From: " + "<"*5000, "to": "To: " + "a,"*5000}.items():
    for n in (1, 2, 4):
        msg = (h * 1 + ("x" * 0) + "\n\nbody").encode()
        msg = (h.split(": ",1)[0] + ": " + h.split(": ",1)[1]*n + "\n\nbody").encode()
        t = time.time(); ep.decode_email_bytes(msg); print(name, n, round(time.time()-t, 3))

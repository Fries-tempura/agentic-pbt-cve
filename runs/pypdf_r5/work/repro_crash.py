import io
from pypdf import PdfReader, PdfWriter

w = PdfWriter()
w.add_blank_page(100, 100)
buf = io.BytesIO(); w.write(buf)
good = buf.getvalue()

cases = {
    "startxref NUL": good.replace(b"startxref\n", b"startxref\x00"),
    "trailer not a dict": good.replace(b"trailer\n<<", b"trailer\n1 <<"),
    "/Size not int": good.replace(b"/Root", b"/Rxxt").replace(b"/Size ", b"/Size /X %"),
}
for name, data in cases.items():
    try:
        r = PdfReader(io.BytesIO(data))
        len(r.pages)
        print(name, "OK")
    except Exception as e:
        print(name, "->", type(e).__module__, type(e).__name__, e)

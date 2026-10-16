import io, time, zlib
from pypdf import PdfReader

def make_pdf(size):
    head = b"%PDF-1.5\n"
    o1 = len(head); obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    o2 = o1 + len(obj1); obj2 = b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    o3 = o2 + len(obj2)
    rows = b"".join(bytes([1]) + o.to_bytes(2, "big") + b"\x00" for o in (0, o1, o2, o3))
    data = zlib.compress(rows)
    xref = (b"3 0 obj\n<< /Type /XRef /Size %d /W [1 2 1] /Root 1 0 R /Filter /FlateDecode /Length %d >>\nstream\n"
            % (size, len(data)) + data + b"\nendstream\nendobj\nstartxref\n%d\n%%%%EOF\n" % o3)
    return head + obj1 + obj2 + xref

for size in (10**5, 10**6, 10**7):
    t = time.time()
    PdfReader(io.BytesIO(make_pdf(size)))
    print(size, f"{time.time() - t:.2f}s")

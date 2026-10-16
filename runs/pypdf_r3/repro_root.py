import io, time, logging
logging.disable(logging.CRITICAL)
from pypdf import PdfReader
from pdfgen import build_pdf
for size in [10, 1000, 10000, 100000]:
    data = build_pdf([b"<< /Type /Foo /Pages 2 0 R >>", b"<< /Type /Pages /Kids [] /Count 0 >>"], include_root=False, size=size)
    r = PdfReader(io.BytesIO(data))
    t = time.time()
    try:
        r.root_object
    except Exception as e:
        print(type(e).__name__, e)
    print(size, round(time.time() - t, 2), "s", len(data), "bytes")

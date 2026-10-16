import io, time, logging
logging.disable(logging.CRITICAL)
from pypdf import PdfReader
from test_reader import build_pdf

for size in [10**3, 10**5, 10**6]:
    data = build_pdf([b"<< /Type /Pages /Kids [] /Count 0 >>"], b"/Size %d" % size)
    t = time.perf_counter()
    try:
        r = PdfReader(io.BytesIO(data)); len(r.pages)
    except Exception as e:
        pass
    print(f"/Size {size}: file={len(data)}B elapsed={time.perf_counter()-t:.3f}s")

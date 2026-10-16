import io, time, logging, cProfile, pstats
logging.disable(logging.CRITICAL)
from pypdf import PdfReader
from test_reader import build_pdf
data = build_pdf([b"<< /Type /Pages /Kids [] /Count 0 >>"], b"/Size 300000")
r = PdfReader(io.BytesIO(data))
pr = cProfile.Profile(); pr.enable()
t = time.perf_counter()
try: len(r.pages)
except Exception as e: print("exc:", type(e).__name__, e)
print(f"{len(data)}-byte file /Size 300000: {time.perf_counter()-t:.2f}s")
pr.disable()
pstats.Stats(pr).sort_stats("tottime").print_stats(8)

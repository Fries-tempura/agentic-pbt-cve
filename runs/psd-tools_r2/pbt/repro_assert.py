import zlib
from psd_tools.compression import decompress
from psd_tools.constants import Compression
out = decompress(zlib.compress(b"\x01\x02\x03"), Compression.ZIP, 10, 10, 8)
print(len(out))  # expected 100
out = decompress(b"", Compression.RLE, 10, 10, 8)
print(len(out))

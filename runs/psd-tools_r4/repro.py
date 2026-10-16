from psd_tools.compression import compress, decompress, decode_rle
from psd_tools.compression import rle, _rle
from psd_tools.constants import Compression
from PIL import Image

# Bug 1: depth=1 RLE drops padded row bytes
data = b"\xff\x80"  # one 9-pixel bitmap row, padded to 2 bytes
c = compress(data, Compression.RLE, 9, 1, 1, 1)
out = decompress(c, Compression.RLE, 9, 1, 1, 1)
print("bitmap:", data, "->", out)
try:
    Image.frombytes("1", (9, 1), out, "raw", "1;I")
except Exception as e:
    print("PIL:", type(e).__name__, e)

# Bug 2: truncated repeat run
bad = b"\x00\x00\xbc"
for impl in (rle, _rle):
    try:
        impl.decode(bad, 70)
    except Exception as e:
        print(impl.__name__, type(e).__name__, e)
try:
    decode_rle(b"\x00\x03" + bad, 70, 1, 8, 1)
except Exception as e:
    print("decode_rle:", type(e).__name__, e)

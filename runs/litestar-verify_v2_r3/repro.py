import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore, _safe_file_name

print(repr(_safe_file_name('𓑠')), '𓑠'.isalnum())
print(_safe_file_name("-"), _safe_file_name("45"), _safe_file_name("ﬁ"), _safe_file_name("fi"))

async def main(d):
    s = FileStore(Path(d))
    await s.set("-", b"dash"); await s.set("45", b"forty-five")
    print("get('-') =", await s.get("-"))
    await s.set("ﬁ", b"lig"); await s.set("fi", b"plain")
    print("get('ﬁ') =", await s.get("ﬁ"))
    await s.set('𓑠', b"v"); print("get(hieroglyph) =", await s.get('𓑠'))
    await s.set("x"*300, b"v"); print("long:", await s.get("x"*300))
    child = s.with_namespace("ns"); await child.set("k", b"c")
    await s.set("ns", b"parent"); print("parent ns:", await s.get("ns"))
    await s.set("n", b"v"); print("expires_in no-expiry:", await s.expires_in("n"))
with tempfile.TemporaryDirectory() as d:
    asyncio.run(main(d))

import asyncio, tempfile, unicodedata
from pathlib import Path
from litestar.stores.file import FileStore, _safe_file_name
k='𓑠'; print(k.isalnum(), unicodedata.unidata_version, _safe_file_name(k))
print(_safe_file_name("a-"), _safe_file_name("a45"), _safe_file_name("user:1"), _safe_file_name("user581"))
async def main():
    with tempfile.TemporaryDirectory() as d:
        s = FileStore(Path(d))
        await s.set("a-", b"first"); await s.set("a45", b"second")
        print(await s.get("a-"))
        await s.set(k, b"x"); print(await s.get(k), list(Path(d).iterdir()))
        await s.set("k"*300, b"x"); print("long:", await s.get("k"*300))
asyncio.run(main())

import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore
async def main(d):
    s = FileStore(Path(d))
    child = s.with_namespace("ns"); await child.set("k", b"c")
    await s.set("ns", b"parent"); print("parent ns:", await s.get("ns"), await s.exists("ns"))
    await s.set("n", b"v"); print("expires_in no-expiry:", await s.expires_in("n"))
    print("exists long:", await s.exists("x"*300))
with tempfile.TemporaryDirectory() as d:
    asyncio.run(main(d))

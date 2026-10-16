import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.set("session:", b"alice")
        await store.set("session58", b"mallory")
        print(await store.get("session:"))
        await store.set("x" * 300, b"v")
        print(await store.get("x" * 300))

asyncio.run(main())

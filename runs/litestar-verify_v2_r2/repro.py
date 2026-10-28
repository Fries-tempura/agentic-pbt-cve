import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.set("/users/alice-profile", b"alice")
        print(await store.get("/users/alice45profile"))
        print(await store.exists("/users/alice45profile"))
        await store.set("2", b"two"); await store.set("²", b"superscript")
        print(await store.get("2"))
        await store.delete("ﬁle"); await store.set("file", b"x"); await store.delete("ﬁle")
        print(await store.get("file"))
        await store.set("", b"v")
        print(await store.get(""))

asyncio.run(main())

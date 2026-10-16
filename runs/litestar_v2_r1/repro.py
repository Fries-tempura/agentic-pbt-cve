import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.set("a.", b"first")
        await store.set("a46", b"second")
        print(await store.get("a."), await store.get("a46"))
        await store.set("ﬁ", b"ligature")
        await store.set("fi", b"plain")
        print(await store.get("ﬁ"))
        await store.delete("a46")
        print(await store.get("a."))

asyncio.run(main())

import asyncio, tempfile
from pathlib import Path
from litestar.stores.file import FileStore

async def main():
    with tempfile.TemporaryDirectory() as d:
        store = FileStore(Path(d))
        await store.set("-", b"secret-of-user-A")
        await store.set("45", b"data-of-user-B")
        print(await store.get("-"))
        await store.set("ﬁ", b"x")
        print(await store.get("fi"))
        await store.set("\U00013460", b"value")
        print(await store.get("\U00013460"))

asyncio.run(main())

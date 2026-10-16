import tempfile
from pathlib import Path

from litestar import Litestar, get
from litestar.stores.file import FileStore
from litestar.testing import create_test_client


@get("/{item:str}", cache=True)
async def handler(item: str) -> str:
    return f"response for {item}"


store = FileStore(Path(tempfile.mkdtemp()))

with create_test_client([handler], stores={"response_cache": store}) as client:
    print(client.get("/a-b").text)
    print(client.get("/a45b").text)

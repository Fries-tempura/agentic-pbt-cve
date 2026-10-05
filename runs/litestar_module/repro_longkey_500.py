import tempfile
from pathlib import Path

from litestar import Litestar, get
from litestar.stores.file import FileStore
from litestar.testing import create_test_client


@get("/search", cache=True)
async def handler(q: str) -> str:
    return "ok"


store = FileStore(Path(tempfile.mkdtemp()))

with create_test_client([handler], stores={"response_cache": store}, raise_server_exceptions=False) as client:
    r = client.get("/search", params={"q": "a b " * 100})
    print("status:", r.status_code)
    print(r.text[:300])

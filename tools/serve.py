"""Local preview; never use this server for production."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "dist"


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        super().end_headers()

    def send_error(self, code, message=None, explain=None):
        page = ROOT / "404.html"
        if code != 404 or not page.exists():
            return super().send_error(code, message, explain)
        body = page.read_bytes()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


if __name__ == "__main__":
    if not (ROOT / "index.html").exists():
        raise SystemExit("Сначала выполните python tools/build.py")
    server = ThreadingHTTPServer(("127.0.0.1", 4173), partial(Handler, directory=str(ROOT)))
    print("Local: http://127.0.0.1:4173", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

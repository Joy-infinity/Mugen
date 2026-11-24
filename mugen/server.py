"""
The Mugen standalone tarpit server.

Run it and point hostile traffic at it. Humans who wander in get a plain notice
(the server is not your real site); detected bots get slowly fed the infinite
labyrinth.

Resource safety is a first-class concern. A tarpit that holds connections open
can, if careless, be turned against *you* -- an attacker could open thousands of
slow connections to exhaust your server instead of theirs. So:

* A semaphore hard-caps how many bots can be dripped at once. Past the cap,
  extra bots get the content quickly instead of slowly -- we never queue
  unbounded work.
* The drip has a total time budget per response. It cannot hang forever.

Nothing here reaches out to the attacker's machine. Everything happens on your
own server. This is a trap on your property, not a counter-attack.
"""

from __future__ import annotations

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import BoundedSemaphore

from .detector import Detector
from .labyrinth import generate_json_page, generate_page, is_trap_path


class Config:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        drip_bytes: int = 64,
        drip_delay: float = 0.4,
        drip_budget_seconds: float = 30.0,
        max_concurrent_drips: int = 50,
        link_prefix: str = "/",
        detector: Detector | None = None,
        log_stream=sys.stdout,
    ) -> None:
        self.host = host
        self.port = port
        self.drip_bytes = drip_bytes          # bytes sent per chunk
        self.drip_delay = drip_delay          # seconds between chunks
        self.drip_budget = drip_budget_seconds  # hard cap on one response
        self.link_prefix = link_prefix
        self.detector = detector or Detector()
        self.log_stream = log_stream
        self.drip_slots = BoundedSemaphore(max_concurrent_drips)


def _log(cfg: Config, event: str, **fields) -> None:
    record = {"ts": round(time.time(), 3), "event": event, **fields}
    try:
        cfg.log_stream.write(json.dumps(record) + "\n")
        cfg.log_stream.flush()
    except Exception:
        pass  # logging must never crash the server


def make_handler(cfg: Config):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Mugen"
        sys_version = ""  # don't leak Python version

        def log_message(self, *args):  # silence default stderr logging
            pass

        def _client_ip(self) -> str:
            return self.client_address[0] if self.client_address else "unknown"

        def _lower_headers(self) -> dict[str, str]:
            return {k.lower(): v for k, v in self.headers.items()}

        def do_GET(self):  # noqa: N802 (http.server naming)
            ip = self._client_ip()
            ua = self.headers.get("User-Agent", "")
            headers = self._lower_headers()
            path = self.path
            honeypot = is_trap_path(path)

            verdict = cfg.detector.inspect(ip, ua, headers, path, honeypot)

            if not verdict.is_bot:
                _log(cfg, "pass", ip=ip, ua=ua, path=path,
                     score=verdict.score, allowlisted=verdict.allowlisted)
                self._send_human_notice()
                return

            _log(cfg, "trapped", ip=ip, ua=ua, path=path, score=verdict.score,
                 reasons=verdict.reasons, ai_agent=verdict.ai_agent)
            wants_json = "application/json" in headers.get("accept", "")
            self._send_labyrinth(path, wants_json)

        # Treat HEAD like GET's decision but with no body.
        def do_HEAD(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()

        def _send_human_notice(self):
            body = (
                "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
                "<title>Mugen</title></head><body>"
                "<h1>Nothing to see here</h1>"
                "<p>This endpoint is protected by Mugen, an anti-bot tarpit. "
                "If you are a human and reached this by mistake, you can close "
                "this page.</p></body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _send_labyrinth(self, path: str, wants_json: bool = False):
            if wants_json:
                page = generate_json_page(path, cfg.link_prefix).encode("utf-8")
                content_type = "application/json; charset=utf-8"
            else:
                page = generate_page(path, cfg.link_prefix).encode("utf-8")
                content_type = "text/html; charset=utf-8"

            # If all drip slots are busy, don't add to the slow load -- send it
            # promptly so we never build an unbounded backlog of slow workers.
            slow = cfg.drip_slots.acquire(blocking=False)
            try:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                # Deliberately no Content-Length: we stream an open-ended body.
                self.end_headers()

                if not slow:
                    self._write_fast(page)
                    return

                self._write_slow(page)
            finally:
                if slow:
                    cfg.drip_slots.release()

        def _write_fast(self, page: bytes):
            try:
                self.wfile.write(page)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _write_slow(self, page: bytes):
            deadline = time.monotonic() + cfg.drip_budget
            try:
                for i in range(0, len(page), cfg.drip_bytes):
                    if time.monotonic() > deadline:
                        # Out of budget: flush the rest and stop holding the line.
                        self.wfile.write(page[i:])
                        self.wfile.flush()
                        return
                    self.wfile.write(page[i:i + cfg.drip_bytes])
                    self.wfile.flush()
                    time.sleep(cfg.drip_delay)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the bot gave up; that's a win

    return Handler


def serve(cfg: Config | None = None) -> None:
    cfg = cfg or Config()
    handler = make_handler(cfg)
    httpd = ThreadingHTTPServer((cfg.host, cfg.port), handler)
    httpd.daemon_threads = True
    _log(cfg, "start", host=cfg.host, port=cfg.port)
    print(f"Mugen tarpit listening on http://{cfg.host}:{cfg.port}", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        _log(cfg, "stop")

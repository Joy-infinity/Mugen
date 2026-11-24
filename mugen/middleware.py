"""
WSGI middleware: bolt Mugen onto an existing Python site.

Wrap your WSGI app and Mugen inspects every request first. Humans pass straight
through to your real app; detected bots are diverted into the labyrinth and
never reach your real routes.

Works with any WSGI framework (Flask, Django, Bottle, raw WSGI). Example for
Flask is in examples/flask_example.py.

Note: the middleware returns the labyrinth page in one piece rather than
slow-dripping it. Slow-drip needs control over the raw socket, which WSGI does
not portably give you; the standalone server (server.py) is the right tool when
you want the drip. The middleware still wastes the bot's time by feeding it an
infinite maze -- just without the per-byte delay.
"""

from __future__ import annotations

from .detector import Detector
from .labyrinth import generate_json_page, generate_page, is_trap_path


class MugenMiddleware:
    def __init__(self, app, detector: Detector | None = None,
                 link_prefix: str = "/", on_trap=None):
        """
        Parameters
        ----------
        app:
            The WSGI application to protect.
        detector:
            A configured Detector, or None for defaults.
        link_prefix:
            Base path the maze links hang off of.
        on_trap:
            Optional callback(environ, verdict) invoked when a bot is trapped,
            e.g. to record the IP for firewalling. Must not raise.
        """
        self.app = app
        self.detector = detector or Detector()
        self.link_prefix = link_prefix
        self.on_trap = on_trap

    def _ip(self, environ) -> str:
        # Honor a reverse proxy's forwarded IP if present, else the socket peer.
        fwd = environ.get("HTTP_X_FORWARDED_FOR", "")
        if fwd:
            return fwd.split(",")[0].strip()
        return environ.get("REMOTE_ADDR", "unknown")

    def _headers(self, environ) -> dict[str, str]:
        out = {}
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                name = key[5:].replace("_", "-").lower()
                out[name] = value
        return out

    def __call__(self, environ, start_response):
        ip = self._ip(environ)
        ua = environ.get("HTTP_USER_AGENT", "")
        path = environ.get("PATH_INFO", "/")
        headers = self._headers(environ)
        honeypot = is_trap_path(path)

        verdict = self.detector.inspect(ip, ua, headers, path, honeypot)

        if not verdict.is_bot:
            return self.app(environ, start_response)

        if self.on_trap:
            try:
                self.on_trap(environ, verdict)
            except Exception:
                pass

        wants_json = "application/json" in environ.get("HTTP_ACCEPT", "")
        if wants_json:
            page = generate_json_page(path, self.link_prefix).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        else:
            page = generate_page(path, self.link_prefix).encode("utf-8")
            content_type = "text/html; charset=utf-8"

        start_response("200 OK", [
            ("Content-Type", content_type),
            ("Content-Length", str(len(page))),
            ("Cache-Control", "no-store"),
        ])
        return [page]

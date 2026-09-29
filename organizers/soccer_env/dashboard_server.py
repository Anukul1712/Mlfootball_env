from __future__ import annotations

import copy
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ASSET_DIRECTORY = Path(__file__).resolve().parent.parent / "dashboard"


class DashboardData:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.snapshot: dict[str, Any] = {
            "event_name": "AI Soccer Arena",
            "status": "starting",
            "completed_matches": 0,
            "total_matches": 0,
            "active_match": None,
            "active_state": None,
            "phase": "starting",
            "announcement": "Preparing the arena",
            "countdown": None,
            "last_events": [],
            "fixtures": [],
            "standings": [],
            "error": None,
        }

    def update(self, snapshot: dict[str, Any]) -> None:
        with self.lock:
            self.snapshot = copy.deepcopy(snapshot)

    def fail(self, error: Exception) -> None:
        with self.lock:
            self.snapshot["status"] = "failed"
            self.snapshot["error"] = str(error)

    def get(self) -> dict[str, Any]:
        with self.lock:
            return copy.deepcopy(self.snapshot)


def _handler_for(data: DashboardData) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/dashboard":
                self._json(data.get())
            elif path in {"/", "/index.html"}:
                self._asset("index.html", "text/html; charset=utf-8")
            elif path == "/dashboard.js":
                self._asset("dashboard.js", "text/javascript; charset=utf-8")
            elif path == "/style.css":
                self._asset("style.css", "text/css; charset=utf-8")
            else:
                self.send_error(404)

        def _asset(self, filename: str, content_type: str) -> None:
            try:
                body = (ASSET_DIRECTORY / filename).read_bytes()
            except OSError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, value: Any) -> None:
            body = json.dumps(value, separators=(",", ":")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    return DashboardHandler


def serve_dashboard(data: DashboardData, port: int = 0, open_browser: bool = True) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), _handler_for(data))
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Tournament dashboard: {url}")
    print("Press Ctrl+C in this terminal to close the dashboard.")
    if open_browser:
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print("\nDashboard closed.")
    finally:
        server.server_close()

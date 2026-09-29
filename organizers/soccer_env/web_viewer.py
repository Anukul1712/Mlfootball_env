from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ASSET_DIRECTORY = Path(__file__).resolve().parent.parent / "viewer"


def load_replay(path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = Path(path)
    metadata: dict[str, Any] = {}
    frames: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on line {line_number}: {error}") from error
            if record.get("type") == "match_start":
                metadata = record
                frames.append({"state": record["initial_state"], "events": [], "actions": {}})
            elif record.get("type") == "iteration":
                frames.append(
                    {
                        "state": record["state_after"],
                        "events": record.get("events", []),
                        "actions": record.get("actions_applied", {}),
                    }
                )
    if not metadata or not frames:
        raise ValueError("This file is not a valid AI Soccer Arena replay")
    return metadata, frames


class ViewerData:
    def __init__(
        self,
        mode: str,
        metadata: dict[str, Any] | None = None,
        frames: list[dict[str, Any]] | None = None,
    ):
        self.mode = mode
        self.metadata = metadata or {}
        self.frames = frames or []
        self.state: dict[str, Any] | None = None
        self.result: dict[str, Any] | None = None
        self.error: str | None = None
        self.events: list[dict[str, Any]] = []
        self.actions: dict[str, Any] = {}
        self.event_history: list[dict[str, Any]] = []
        self.lock = threading.Lock()

    def update_state(self, state: dict[str, Any]) -> None:
        with self.lock:
            self.state = state

    def update_frame(self, state: dict[str, Any], info: dict[str, Any]) -> None:
        with self.lock:
            self.state = state
            self.events = info.get("events", [])
            self.actions = info.get("actions_applied", {})
            if self.events:
                self.event_history.append(
                    {
                        "iteration": state["iteration"],
                        "events": self.events,
                        "score": state["score"],
                        "ball": state["ball"],
                    }
                )
                self.event_history = self.event_history[-100:]

    def finish(self, result: dict[str, Any]) -> None:
        with self.lock:
            self.result = result

    def fail(self, error: Exception) -> None:
        with self.lock:
            self.error = str(error)

    def live_snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "state": self.state,
                "events": self.events,
                "actions": self.actions,
                "event_history": self.event_history,
                "result": self.result,
                "error": self.error,
            }


def _handler_for(data: ViewerData) -> type[BaseHTTPRequestHandler]:
    class ViewerHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/info":
                self._json({"mode": data.mode, "metadata": data.metadata})
            elif path == "/api/state":
                self._json(data.live_snapshot())
            elif path == "/api/replay":
                self._json({"metadata": data.metadata, "frames": data.frames})
            elif path in {"/", "/index.html"}:
                self._asset("index.html", "text/html; charset=utf-8")
            elif path == "/viewer.js":
                self._asset("viewer.js", "text/javascript; charset=utf-8")
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

    return ViewerHandler


def serve_viewer(data: ViewerData, port: int = 0, open_browser: bool = True) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), _handler_for(data))
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"
    print(f"Viewer: {url}")
    print("Press Ctrl+C in this terminal to close the viewer.")
    if open_browser:
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print("\nViewer closed.")
    finally:
        server.server_close()

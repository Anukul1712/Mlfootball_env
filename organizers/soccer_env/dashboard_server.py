from __future__ import annotations

import copy
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


ASSET_DIRECTORY = Path(__file__).resolve().parent.parent / "dashboard"


class TournamentControl:
    """Thread-safe match and games-per-tie controls for the event runner."""

    def __init__(self, rounds: int = 4) -> None:
        self.condition = threading.Condition()
        self.started = False
        self.paused = True
        self.step_budget = 0
        self.rounds = max(1, min(20, int(rounds)))
        self.speed = 1.0

    def state(self) -> dict[str, Any]:
        with self.condition:
            return {
                "started": self.started,
                "paused": self.paused,
                "rounds": self.rounds,
                "speed": self.speed,
            }

    def apply(self, command: dict[str, Any]) -> dict[str, Any]:
        action = str(command.get("action", "")).lower()
        with self.condition:
            if action == "configure" and not self.started:
                self.rounds = max(1, min(20, int(command.get("rounds", self.rounds))))
            elif action in {"start", "play"}:
                self.started = True
                self.paused = False
                self.step_budget = 0
            elif action == "pause":
                self.paused = True
            elif action == "step":
                self.started = True
                self.paused = True
                self.step_budget += 1
            elif action == "speed":
                self.speed = max(0.1, min(8.0, float(command.get("speed", 1.0))))
            else:
                raise ValueError(f"Unsupported control action: {action or '(empty)'}")
            self.condition.notify_all()
            return self.state_unlocked()

    def state_unlocked(self) -> dict[str, Any]:
        return {
            "started": self.started,
            "paused": self.paused,
            "rounds": self.rounds,
            "speed": self.speed,
        }

    def checkpoint(self) -> None:
        with self.condition:
            while not self.started or (self.paused and self.step_budget <= 0):
                self.condition.wait(timeout=0.5)
            if self.paused and self.step_budget > 0:
                self.step_budget -= 1

    def wait_for_start(self, rounds_changed: Callable[[int], None]) -> int:
        """Wait for Start while publishing every pre-start games-per-tie change."""
        published_rounds: int | None = None
        while True:
            with self.condition:
                while not self.started and self.rounds == published_rounds:
                    self.condition.wait(timeout=0.5)
                rounds = self.rounds
                started = self.started
            if rounds != published_rounds:
                rounds_changed(rounds)
                published_rounds = rounds
            if started:
                return rounds

    def delay(self, normal_delay: float) -> float:
        with self.condition:
            return normal_delay / self.speed


class DashboardData:
    def __init__(self, rounds: int = 4) -> None:
        self.lock = threading.Lock()
        self.control = TournamentControl(rounds)
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
            "control": self.control.state(),
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
            snapshot = copy.deepcopy(self.snapshot)
        snapshot["control"] = self.control.state()
        return snapshot

    def command(self, value: dict[str, Any]) -> dict[str, Any]:
        state = self.control.apply(value)
        with self.lock:
            self.snapshot["control"] = state
        return state


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

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/control":
                self.send_error(404)
                return
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 4096)
                command = json.loads(self.rfile.read(length) or b"{}")
                self._json({"ok": True, "control": data.command(command)})
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self.send_response(400)
                self._json({"ok": False, "error": str(error)}, response_started=True)

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

        def _json(self, value: Any, response_started: bool = False) -> None:
            body = json.dumps(value, separators=(",", ":")).encode("utf-8")
            if not response_started:
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

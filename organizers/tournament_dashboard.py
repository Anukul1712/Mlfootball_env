from __future__ import annotations

import argparse
import asyncio
import json
import threading
from pathlib import Path

from run_event import run_event
from soccer_env.dashboard_server import DashboardData, serve_dashboard

BASE_DIRECTORY = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an event with a live localhost tournament dashboard")
    parser.add_argument("--config", default=str(BASE_DIRECTORY / "config" / "event.json"))
    parser.add_argument("--port", type=int, default=0, help="Local port; zero chooses an available port")
    parser.add_argument("--no-browser", action="store_true", help="Print the URL without opening it")
    args = parser.parse_args()
    event_settings = json.loads(Path(args.config).read_text(encoding="utf-8"))
    data = DashboardData(rounds=int(event_settings.get("games_per_tie", 1)))

    def run_event_thread() -> None:
        try:
            asyncio.run(run_event(Path(args.config), status_callback=data.update, control=data.control))
        except Exception as error:
            data.fail(error)

    threading.Thread(target=run_event_thread, daemon=True).start()
    serve_dashboard(data, args.port, not args.no_browser)


if __name__ == "__main__":
    main()

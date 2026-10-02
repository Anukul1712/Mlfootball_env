from __future__ import annotations

import argparse
import asyncio
import json
import threading
from datetime import datetime
from pathlib import Path

from run_event import run_event
from soccer_env.dashboard_server import DashboardData, serve_dashboard
from soccer_env.tournament_setup import build_event, discover_submissions


BASE_DIRECTORY = Path(__file__).resolve().parent


def demo_competitors() -> list[dict[str, object]]:
    return [
        {"name": "Balanced United RL", "command": ["python", "-m", "agents.reinforcement_bot"], "working_directory": str(BASE_DIRECTORY)},
        {"name": "Tactical Rovers", "command": ["python", "-m", "agents.practice_bot"], "working_directory": str(BASE_DIRECTORY)},
        {"name": "Blitz Strikers", "command": ["python", "-m", "agents.striker_bot"], "working_directory": str(BASE_DIRECTORY)},
        {"name": "Counter City", "command": ["python", "-m", "agents.counter_bot"], "working_directory": str(BASE_DIRECTORY)},
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover accepted teams and start the complete visual tournament")
    parser.add_argument("--demo", action="store_true", help="Use the four included organizer bots")
    parser.add_argument("--fast", action="store_true", help="Disable presentation pauses for a technical dry run")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    settings_path = BASE_DIRECTORY / "config" / "tournament_settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    competitors = demo_competitors() if args.demo else discover_submissions(BASE_DIRECTORY / "submissions")
    if len(competitors) < 2:
        raise SystemExit(
            "Tournament not started: fewer than two accepted teams were found.\n"
            "Put submission ZIPs in organizers/incoming and run: python organizers/accept_submissions.py\n"
            "For the built-in visual demonstration, run: python organizers/start_tournament.py --demo"
        )
    if args.fast:
        settings.update(
            presentation_delay_seconds=0,
            event_countdown_seconds=0,
            match_countdown_seconds=0,
            goal_pause_seconds=0,
            between_matches_seconds=0,
        )

    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    event = build_event(
        settings,
        competitors,
        BASE_DIRECTORY / "config" / "game.json",
        BASE_DIRECTORY / "logs" / "tournaments" / run_id,
    )
    generated_path = BASE_DIRECTORY / "config" / "generated_event.json"
    generated_path.write_text(json.dumps(event, indent=2), encoding="utf-8")
    print("Teams:")
    for competitor in competitors:
        print(f"  - {competitor['name']}")
    print(f"Tournament file: {generated_path}")

    data = DashboardData(rounds=int(settings.get("games_per_tie", 1)))

    def event_thread() -> None:
        try:
            asyncio.run(run_event(generated_path, status_callback=data.update, control=data.control))
        except Exception as error:
            data.fail(error)

    threading.Thread(target=event_thread, daemon=True).start()
    serve_dashboard(data, args.port, not args.no_browser)


if __name__ == "__main__":
    main()

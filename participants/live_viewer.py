from __future__ import annotations

import argparse
import asyncio
import json
import threading
from pathlib import Path

from soccer_env import GameConfig
from soccer_env.match_runner import Competitor, load_competitor, play_match
from soccer_env.web_viewer import ViewerData, serve_viewer


BASE_DIRECTORY = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch a participant practice match in a browser")
    parser.add_argument("--config", default=str(BASE_DIRECTORY / "config" / "demo_match.json"))
    parser.add_argument("--submission", help="submission.json to use as player 1")
    parser.add_argument("--opponent", choices=("organizer-rl", "simple"), default="organizer-rl")
    parser.add_argument("--seed", type=int, help="Override the match seed")
    parser.add_argument("--delay", type=float, default=0.06, help="Seconds between displayed iterations")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    match_path = Path(args.config).resolve()
    match = json.loads(match_path.read_text(encoding="utf-8"))
    seed = int(args.seed if args.seed is not None else match["seed"])
    if args.submission:
        submission_path = Path(args.submission).resolve()
        player_1 = load_competitor(
            json.loads(submission_path.read_text(encoding="utf-8")), submission_path.parent
        )
    else:
        player_1 = load_competitor(match["player_1"], BASE_DIRECTORY)
    player_2 = (
        load_competitor(match["player_2"], BASE_DIRECTORY)
        if args.opponent == "organizer-rl"
        else Competitor(
            "Simple Readable Baseline",
            ["python", "-m", "reference_bot.bot"],
            str(BASE_DIRECTORY),
        )
    )
    data = ViewerData(
        "live",
        metadata={
            "seed": seed,
            "players": {
                "player_1": player_1.name,
                "player_2": player_2.name,
            },
        },
    )

    def run() -> None:
        try:
            game_path = Path(match["game_config"])
            if not game_path.is_absolute():
                game_path = match_path.parent / game_path
            result = asyncio.run(
                play_match(
                    GameConfig.from_json(game_path),
                    seed,
                    player_1,
                    player_2,
                    timeout_seconds=float(match.get("action_timeout_seconds", 2.0)),
                    log_directory=BASE_DIRECTORY / match.get("log_directory", "logs"),
                    state_callback=data.update_state,
                    frame_callback=data.update_frame,
                    iteration_delay_seconds=max(0.0, args.delay),
                )
            )
            data.finish(result)
        except Exception as error:
            data.fail(error)

    threading.Thread(target=run, daemon=True).start()
    serve_viewer(data, args.port, not args.no_browser)


if __name__ == "__main__":
    main()

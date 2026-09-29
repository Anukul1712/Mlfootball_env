from __future__ import annotations

import argparse
import asyncio
import json
import threading
from pathlib import Path

from soccer_env import GameConfig
from soccer_env.match_runner import load_competitor, play_match
from soccer_env.web_viewer import ViewerData, serve_viewer

BASE_DIRECTORY = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch a live AI Soccer Arena match in a browser")
    parser.add_argument("--config", default=str(BASE_DIRECTORY / "config" / "demo_match.json"))
    parser.add_argument("--delay", type=float, default=0.06, help="Seconds between displayed iterations")
    parser.add_argument("--port", type=int, default=0, help="Local port; zero chooses an available port")
    parser.add_argument("--no-browser", action="store_true", help="Print the URL without opening it")
    args = parser.parse_args()

    match_path = Path(args.config).resolve()
    match = json.loads(match_path.read_text(encoding="utf-8"))
    data = ViewerData(
        "live",
        metadata={
            "seed": int(match["seed"]),
            "players": {
                "player_1": match["player_1"]["name"],
                "player_2": match["player_2"]["name"],
            },
        },
    )

    def run_match_thread() -> None:
        try:
            game_config_path = Path(match["game_config"])
            if not game_config_path.is_absolute():
                game_config_path = match_path.parent / game_config_path
            config = GameConfig.from_json(game_config_path)
            result = asyncio.run(
                play_match(
                    game_config=config,
                    seed=int(match["seed"]),
                    player_1=load_competitor(match["player_1"], BASE_DIRECTORY),
                    player_2=load_competitor(match["player_2"], BASE_DIRECTORY),
                    timeout_seconds=float(match.get("action_timeout_seconds", 2.0)),
                    log_directory=BASE_DIRECTORY / match.get("log_directory", "logs"),
                    show_each_iteration=False,
                    state_callback=data.update_state,
                    frame_callback=data.update_frame,
                    iteration_delay_seconds=max(0.0, args.delay),
                )
            )
            data.finish(result)
        except Exception as error:
            data.fail(error)

    threading.Thread(target=run_match_thread, daemon=True).start()
    serve_viewer(data, port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()

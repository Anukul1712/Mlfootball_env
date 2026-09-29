from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from soccer_env import GameConfig
from soccer_env.match_runner import load_competitor, play_match

BASE_DIRECTORY = Path(__file__).resolve().parent


def relative_to_config(config_path: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else config_path.parent / path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one deterministic AI Soccer Arena match")
    parser.add_argument("--config", default=str(BASE_DIRECTORY / "config" / "demo_match.json"), help="Match JSON file")
    args = parser.parse_args()

    match_path = Path(args.config).resolve()
    match = json.loads(match_path.read_text(encoding="utf-8"))
    game_config = GameConfig.from_json(relative_to_config(match_path, match["game_config"]))
    result = asyncio.run(
        play_match(
            game_config=game_config,
            seed=int(match["seed"]),
            player_1=load_competitor(match["player_1"], BASE_DIRECTORY),
            player_2=load_competitor(match["player_2"], BASE_DIRECTORY),
            timeout_seconds=float(match.get("action_timeout_seconds", 2.0)),
            log_directory=BASE_DIRECTORY / match.get("log_directory", "logs"),
            show_each_iteration=bool(match.get("show_each_iteration", False)),
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

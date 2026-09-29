from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
import json
from pathlib import Path

from soccer_env import GameConfig
from soccer_env.match_runner import Competitor, load_competitor, play_match

BASE_DIRECTORY = Path(__file__).resolve().parent


async def validate(args: argparse.Namespace) -> int:
    submission_path = Path(args.submission).resolve()
    submission_raw = json.loads(submission_path.read_text(encoding="utf-8"))
    submission = load_competitor(submission_raw, submission_path.parent)
    if args.working_directory:
        submission_directory = Path(args.working_directory).resolve()
    elif submission.working_directory:
        submission_directory = Path(submission.working_directory)
        if not submission_directory.is_absolute():
            submission_directory = (submission_path.parent / submission_directory).resolve()
    else:
        submission_directory = submission_path.parent
    submission = replace(submission, working_directory=str(submission_directory))
    practice = Competitor(
        "Official Practice Bot",
        [args.python, "-m", "agents.practice_bot"],
        working_directory=str(BASE_DIRECTORY),
    )
    config = GameConfig.from_json(args.game_config)
    seeds = [args.seed + offset for offset in range(args.matches_per_side)]
    failures = 0
    matches = 0

    for seed in seeds:
        for player_1, player_2 in ((submission, practice), (practice, submission)):
            matches += 1
            result = await play_match(
                config,
                seed,
                player_1,
                player_2,
                timeout_seconds=args.timeout,
                log_directory=args.log_directory,
            )
            submission_side = "player_1" if player_1.name == submission.name else "player_2"
            errors = result["action_error_counts"][submission_side]
            failures += errors
            print(
                f"match={matches} seed={seed} side={submission_side} "
                f"score={result['score']['player_1']}-{result['score']['player_2']} action_errors={errors}"
            )

    print(f"\nValidation complete: matches={matches}, participant action errors={failures}")
    if failures:
        print("FAILED: inspect the replay action_errors fields and fix the bot before submission.")
        return 1
    print("PASSED: the bot completed every checked iteration within the protocol and timeout.")
    return 0


def main() -> None:
    import sys

    parser = argparse.ArgumentParser(description="Validate a participant bot against the official practice bot")
    parser.add_argument("--submission", default=str(BASE_DIRECTORY / "config" / "submission.example.json"))
    parser.add_argument("--game-config", default=str(BASE_DIRECTORY / "config" / "game.json"))
    parser.add_argument("--matches-per-side", type=int, default=2)
    parser.add_argument("--seed", type=int, default=7000)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--log-directory", default=str(BASE_DIRECTORY / "logs" / "validation"))
    parser.add_argument("--working-directory", help="Directory from which the participant command is launched")
    parser.add_argument("--python", default=sys.executable, help=argparse.SUPPRESS)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(validate(args)))


if __name__ == "__main__":
    main()

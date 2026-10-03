from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from soccer_env import GameConfig
from soccer_env.match_runner import Competitor, load_competitor, play_match


BASE_DIRECTORY = Path(__file__).resolve().parent


async def validate(args: argparse.Namespace) -> int:
    descriptor_path = Path(args.submission).resolve()
    participant = load_competitor(
        json.loads(descriptor_path.read_text(encoding="utf-8")), descriptor_path.parent
    )
    reference = Competitor(
        "Balanced United RL Reference",
        [sys.executable, "-m", "organizer_rl_bot.bot"],
        str(BASE_DIRECTORY),
    )
    config = GameConfig.from_json(BASE_DIRECTORY / "config" / "game.json")
    failures = 0
    matches = 0
    for offset in range(args.matches_per_side):
        seed = args.seed + offset
        for player_1, player_2 in ((participant, reference), (reference, participant)):
            matches += 1
            result = await play_match(
                config,
                seed,
                player_1,
                player_2,
                args.timeout,
                BASE_DIRECTORY / "logs" / "validation",
            )
            side = "player_1" if player_1.name == participant.name else "player_2"
            errors = result["action_error_counts"][side]
            failures += errors
            print(
                f"match={matches} seed={seed} side={side} "
                f"score={result['score']['player_1']}-{result['score']['player_2']} action_errors={errors}"
            )
    print(f"Validation complete: matches={matches}, participant action errors={failures}")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a submission locally on both sides")
    parser.add_argument(
        "--submission",
        default=str(BASE_DIRECTORY / "submission_kit" / "submission.json"),
    )
    parser.add_argument("--matches-per-side", type=int, default=1)
    parser.add_argument("--seed", type=int, default=7000)
    parser.add_argument("--timeout", type=float, default=2.0)
    raise SystemExit(asyncio.run(validate(parser.parse_args())))


if __name__ == "__main__":
    main()

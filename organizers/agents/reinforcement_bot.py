"""Runs the trained full-action-space reinforcement-learning policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from soccer_env.reinforcement import ReinforcementPolicy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default=str(Path(__file__).resolve().parent.parent / "models" / "balanced_rl.json"),
    )
    parser.add_argument("--safety-margin", type=float, help="Override the model safety margin")
    parser.add_argument("--epsilon", type=float, help="Override seeded evaluation exploration")
    args = parser.parse_args()
    bot = ReinforcementPolicy.load(args.model)
    if args.safety_margin is not None:
        bot.safety_margin = max(0.0, args.safety_margin)
    if args.epsilon is not None:
        bot.evaluation_epsilon = max(0.0, min(1.0, args.epsilon))
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("type") == "match_end":
            return
        if message.get("type") == "observation":
            action = bot.decide(message["observation"])
            print(json.dumps(action, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()

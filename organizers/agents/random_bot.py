"""Seeded random example agent using the organizer JSON Lines protocol."""

from __future__ import annotations

import argparse
import json
import random
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("type") == "match_end":
            return
        if message.get("type") != "observation":
            continue
        observation = message["observation"]
        action = {"move": rng.choice(observation["action_space"]["move"])}
        if observation["state"]["ball"]["possession"] == observation["player_id"]:
            action["kick"] = {
                "direction": rng.choice(observation["action_space"]["kick"]["direction"]),
                "power": rng.choice(observation["action_space"]["kick"]["power"]),
            }
        print(json.dumps(action, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()

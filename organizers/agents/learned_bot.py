"""Runs a policy produced by train_bot.py through the match protocol."""

from __future__ import annotations

import argparse
import json
import sys

from soccer_env.bots import QLearningBot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/trained_bot.json")
    args = parser.parse_args()
    bot = QLearningBot.load(args.model)
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("type") == "match_end":
            return
        if message.get("type") == "observation":
            print(json.dumps(bot.decide(message["observation"]), separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()

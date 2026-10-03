from __future__ import annotations

import argparse
import json
import sys

from .policy import DEFAULT_MODEL, OrganizerRLOpponent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the participant copy of Balanced United RL")
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    args = parser.parse_args()
    opponent = OrganizerRLOpponent(args.model)

    for line in sys.stdin:
        try:
            message = json.loads(line)
            if message.get("type") == "match_end":
                return
            if message.get("type") == "observation":
                action = opponent.choose_action(message["observation"])
                print(json.dumps(action, separators=(",", ":")), flush=True)
        except Exception as error:
            print(f"organizer RL opponent error: {error}", file=sys.stderr, flush=True)
            print('{"move":"STAY"}', flush=True)


if __name__ == "__main__":
    main()

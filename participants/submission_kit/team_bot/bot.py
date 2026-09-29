from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .policy import Policy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    policy = Policy.load(Path(args.model))

    for line in sys.stdin:
        try:
            message = json.loads(line)
            if message.get("type") == "match_end":
                return
            if message.get("type") != "observation":
                continue
            action = policy.choose_action(message["observation"])
            print(json.dumps(action, separators=(",", ":")), flush=True)
        except Exception as error:
            # Diagnostics belong on stderr. Return a safe action if one turn fails.
            print(f"bot error: {error}", file=sys.stderr, flush=True)
            print('{"move":"STAY"}', flush=True)


if __name__ == "__main__":
    main()

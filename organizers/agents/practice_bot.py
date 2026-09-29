"""Ready-to-use deterministic simulator opponent using JSON Lines on stdin/stdout."""

from __future__ import annotations

import json
import sys

from soccer_env.bots import practice_action


def main() -> None:
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("type") == "match_end":
            return
        if message.get("type") == "observation":
            print(json.dumps(practice_action(message["observation"]), separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()

"""Aggressive high-press demo team using the JSON Lines match protocol."""

from __future__ import annotations

import json
import sys

from soccer_env.bots import aggressive_action


def main() -> None:
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("type") == "match_end":
            return
        if message.get("type") == "observation":
            action = aggressive_action(message["observation"])
            print(json.dumps(action, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()

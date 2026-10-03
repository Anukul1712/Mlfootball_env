from __future__ import annotations

import json
import sys

from .policy import choose_action


def main() -> None:
    for line in sys.stdin:
        try:
            message = json.loads(line)
            if message.get("type") == "match_end":
                return
            if message.get("type") != "observation":
                continue
            print(json.dumps(choose_action(message["observation"]), separators=(",", ":")), flush=True)
        except Exception as error:
            print(f"reference bot error: {error}", file=sys.stderr, flush=True)
            print('{"move":"STAY"}', flush=True)


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def direction_toward(dx: float, dy: float, dead_zone: float = 1.0) -> str:
    horizontal = "" if abs(dx) <= dead_zone else ("RIGHT" if dx > 0 else "LEFT")
    vertical = "" if abs(dy) <= dead_zone else ("UP" if dy > 0 else "DOWN")
    if vertical and horizontal:
        return f"{vertical}_{horizontal}"
    return vertical or horizontal or "STAY"


@dataclass
class Policy:
    kick_power: int = 3

    @classmethod
    def load(cls, path: Path) -> "Policy":
        values = json.loads(path.read_text(encoding="utf-8"))
        return cls(kick_power=int(values.get("kick_power", 3)))

    def choose_action(self, observation: dict[str, Any]) -> dict[str, Any]:
        player_id = observation["player_id"]
        state = observation["state"]
        player = state["players"][player_id]
        ball = state["ball"]

        if ball["possession"] == player_id:
            attack = observation["attack_direction"]
            allowed_powers = observation["action_space"]["kick"]["power"]
            power = min(max(allowed_powers), max(min(allowed_powers), self.kick_power))
            return {"move": attack, "kick": {"direction": attack, "power": power}}

        return {
            "move": direction_toward(ball["x"] - player["x"], ball["y"] - player["y"])
        }

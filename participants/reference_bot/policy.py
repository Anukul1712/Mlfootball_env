from __future__ import annotations

import math
from typing import Any


DIRECTIONS = {
    "STAY": (0, 0),
    "UP": (0, 1),
    "UP_RIGHT": (1, 1),
    "RIGHT": (1, 0),
    "DOWN_RIGHT": (1, -1),
    "DOWN": (0, -1),
    "DOWN_LEFT": (-1, -1),
    "LEFT": (-1, 0),
    "UP_LEFT": (-1, 1),
}


def direction_toward(dx: float, dy: float, dead_zone: float = 1.0) -> str:
    horizontal = "" if abs(dx) <= dead_zone else ("RIGHT" if dx > 0 else "LEFT")
    vertical = "" if abs(dy) <= dead_zone else ("UP" if dy > 0 else "DOWN")
    return f"{vertical}_{horizontal}" if vertical and horizontal else vertical or horizontal or "STAY"


def safe_move(observation: dict[str, Any], preferred: str) -> str:
    """Pick the legal direction most aligned with the desired direction."""
    state = observation["state"]
    me = state["players"][observation["player_id"]]
    field = state["field"]
    speed = float(field["player_speed"])
    radius = float(field["player_radius"])

    def valid(move: str) -> bool:
        vx, vy = DIRECTIONS[move]
        length = math.hypot(vx, vy) or 1.0
        x, y = me["x"] + vx / length * speed, me["y"] + vy / length * speed
        if x - radius < 0 or x + radius > field["width"] or y - radius < 0 or y + radius > field["height"]:
            return False
        for obstacle in state["obstacles"]:
            nearest_x = min(max(x, obstacle["x"]), obstacle["x"] + obstacle["width"])
            nearest_y = min(max(y, obstacle["y"]), obstacle["y"] + obstacle["height"])
            if math.hypot(x - nearest_x, y - nearest_y) < radius + 0.25:
                return False
        return True

    px, py = DIRECTIONS[preferred]
    choices = [move for move in DIRECTIONS if move != "STAY" and valid(move)]
    if not choices:
        return "STAY"
    return max(choices, key=lambda move: (DIRECTIONS[move][0] * px + DIRECTIONS[move][1] * py, move == preferred))


def choose_action(observation: dict[str, Any]) -> dict[str, Any]:
    """Simple readable baseline: chase, control briefly, evade, then shoot."""
    player_id = observation["player_id"]
    opponent_id = observation["opponent_id"]
    state = observation["state"]
    me = state["players"][player_id]
    opponent = state["players"][opponent_id]
    ball = state["ball"]
    attack = observation["attack_direction"]
    sign = 1 if attack == "UP" else -1

    if ball["possession"] == player_id:
        distance_to_goal = state["field"]["height"] - me["y"] if sign > 0 else me["y"]
        defender_ahead = (
            sign * (opponent["y"] - me["y"]) > 0
            and abs(opponent["x"] - me["x"]) < 12
            and math.hypot(opponent["x"] - me["x"], opponent["y"] - me["y"]) < 55
        )
        side = "LEFT" if opponent["x"] >= me["x"] else "RIGHT"
        carry_direction = f"{attack}_{side}" if defender_ahead else attack
        move = safe_move(observation, carry_direction)
        if distance_to_goal > 50 and int(ball.get("possession_steps", 0)) < 3:
            return {"move": move}
        shot = carry_direction if defender_ahead else direction_toward(
            state["field"]["width"] / 2 - me["x"], sign * distance_to_goal, dead_zone=6
        )
        powers = observation["action_space"]["kick"]["power"]
        return {"move": move, "kick": {"direction": shot, "power": max(powers)}}

    target_x, target_y = ball["x"], ball["y"]
    if ball["status"] == "moving":
        target_x += float(ball["velocity"]["x"])
        target_y += float(ball["velocity"]["y"])
    elif ball["possession"] == opponent_id:
        target_y += -3 if attack == "UP" else 3
        target_x += -3 if opponent["x"] > state["field"]["width"] / 2 else 3
    preferred = direction_toward(target_x - me["x"], target_y - me["y"], dead_zone=0.6)
    return {"move": safe_move(observation, preferred)}

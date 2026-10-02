from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any


DIRECTION_VECTORS = {
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
MOVES = list(DIRECTION_VECTORS)


def direction_toward(dx: float, dy: float, dead_zone: float = 1.0) -> str:
    horizontal = "" if abs(dx) <= dead_zone else ("RIGHT" if dx > 0 else "LEFT")
    vertical = "" if abs(dy) <= dead_zone else ("UP" if dy > 0 else "DOWN")
    if vertical and horizontal:
        return f"{vertical}_{horizontal}"
    return vertical or horizontal or "STAY"


def _safe_move(observation: dict[str, Any], preferred: str) -> str:
    """Choose the closest unblocked direction to the tactical preference."""
    state = observation["state"]
    me = state["players"][observation["player_id"]]
    field = state["field"]
    speed = float(field.get("player_speed", 4.0))
    radius = float(field.get("player_radius", 3.0))
    preferred_vector = DIRECTION_VECTORS[preferred]

    def valid(name: str) -> bool:
        vx, vy = DIRECTION_VECTORS[name]
        length = math.hypot(vx, vy) or 1.0
        x = me["x"] + vx / length * speed
        y = me["y"] + vy / length * speed
        if x - radius < 0 or x + radius > field["width"] or y - radius < 0 or y + radius > field["height"]:
            return False
        for obstacle in state.get("obstacles", []):
            closest_x = min(max(x, obstacle["x"]), obstacle["x"] + obstacle["width"])
            closest_y = min(max(y, obstacle["y"]), obstacle["y"] + obstacle["height"])
            if math.hypot(x - closest_x, y - closest_y) < radius + 0.25:
                return False
        return True

    candidates = [name for name in MOVES if name != "STAY" and valid(name)]
    if not candidates:
        return "STAY"
    return max(
        candidates,
        key=lambda name: (
            DIRECTION_VECTORS[name][0] * preferred_vector[0]
            + DIRECTION_VECTORS[name][1] * preferred_vector[1],
            name == preferred,
        ),
    )


def practice_action(observation: dict[str, Any]) -> dict[str, Any]:
    """Deterministic tactical baseline: intercept, dribble, evade, and shoot."""
    player_id = observation["player_id"]
    opponent_id = observation["opponent_id"]
    state = observation["state"]
    me = state["players"][player_id]
    opponent = state["players"][opponent_id]
    ball = state["ball"]
    if ball["possession"] == player_id:
        attack = observation["attack_direction"]
        sign = 1 if attack == "UP" else -1
        distance_to_goal = state["field"]["height"] - me["y"] if sign > 0 else me["y"]
        opponent_distance = math.hypot(opponent["x"] - me["x"], opponent["y"] - me["y"])
        opponent_ahead = (
            sign * (opponent["y"] - me["y"]) > 0
            and abs(opponent["x"] - me["x"]) < 12
            and opponent_distance < 55
        )
        evade_side = "LEFT" if opponent["x"] >= me["x"] else "RIGHT"
        dribble = f"{attack}_{evade_side}" if opponent_ahead else attack
        move = _safe_move(observation, dribble)
        possession_steps = int(ball.get("possession_steps", 0))

        # Carry briefly to create visibly purposeful attacks, then release the
        # ball. Shoot earlier near goal or when a defender closes the lane.
        if distance_to_goal > 50 and possession_steps < 3:
            return {"move": move}
        kick_direction = dribble if opponent_ahead else direction_toward(
            state["field"]["width"] / 2 - me["x"], sign * distance_to_goal, dead_zone=6.0
        )
        powers = observation["action_space"]["kick"]["power"]
        power = max(powers) if distance_to_goal > 30 else min(powers)
        return {"move": move, "kick": {"direction": kick_direction, "power": power}}

    target_x, target_y = ball["x"], ball["y"]
    if ball["status"] == "moving":
        velocity = ball.get("velocity", {})
        # Lead the ball by one simulation step instead of chasing its old spot.
        target_x += float(velocity.get("x", 0.0))
        target_y += float(velocity.get("y", 0.0))
    elif ball["possession"] == opponent_id:
        # Press from the goal side so contact becomes a tackle rather than a
        # repeated head-on collision.
        defend_sign = -1 if observation["attack_direction"] == "UP" else 1
        target_y += defend_sign * 3.0
        target_x += -3.0 if opponent["x"] > state["field"]["width"] / 2 else 3.0
    preferred = direction_toward(target_x - me["x"], target_y - me["y"], dead_zone=0.6)
    return {"move": _safe_move(observation, preferred)}


def aggressive_action(observation: dict[str, Any]) -> dict[str, Any]:
    """High-press attacker: closes quickly and releases powerful shots early."""
    player_id = observation["player_id"]
    opponent_id = observation["opponent_id"]
    state = observation["state"]
    me = state["players"][player_id]
    opponent = state["players"][opponent_id]
    ball = state["ball"]
    attack = observation["attack_direction"]
    sign = 1 if attack == "UP" else -1

    if ball["possession"] == player_id:
        opponent_in_lane = (
            sign * (opponent["y"] - me["y"]) > 0
            and abs(opponent["x"] - me["x"]) < 14
        )
        if opponent_in_lane:
            side = "LEFT" if opponent["x"] >= me["x"] else "RIGHT"
            direction = f"{attack}_{side}"
        else:
            direction = direction_toward(
                state["field"]["width"] / 2 - me["x"],
                sign * state["field"]["height"],
                dead_zone=5.0,
            )
        return {
            "move": _safe_move(observation, direction),
            "kick": {
                "direction": direction,
                "power": max(observation["action_space"]["kick"]["power"]),
            },
        }

    target_x, target_y = ball["x"], ball["y"]
    if ball["status"] == "moving":
        velocity = ball.get("velocity", {})
        target_x += 2.0 * float(velocity.get("x", 0.0))
        target_y += 2.0 * float(velocity.get("y", 0.0))
    preferred = direction_toward(target_x - me["x"], target_y - me["y"], dead_zone=0.25)
    return {"move": _safe_move(observation, preferred)}


def counter_action(observation: dict[str, Any]) -> dict[str, Any]:
    """Goal-side defender that carries wide before launching counterattacks."""
    player_id = observation["player_id"]
    opponent_id = observation["opponent_id"]
    state = observation["state"]
    me = state["players"][player_id]
    opponent = state["players"][opponent_id]
    ball = state["ball"]
    field = state["field"]
    attack = observation["attack_direction"]
    sign = 1 if attack == "UP" else -1

    if ball["possession"] == player_id:
        side = "RIGHT" if me["x"] <= field["width"] / 2 else "LEFT"
        break_direction = f"{attack}_{side}"
        possession_steps = int(ball.get("possession_steps", 0))
        if possession_steps < 2:
            return {"move": _safe_move(observation, break_direction)}
        goal_direction = direction_toward(
            field["width"] / 2 - me["x"],
            sign * field["height"],
            dead_zone=4.0,
        )
        powers = observation["action_space"]["kick"]["power"]
        return {
            "move": _safe_move(observation, break_direction),
            "kick": {"direction": goal_direction, "power": max(powers)},
        }

    if ball["possession"] == opponent_id:
        distance_to_opponent = math.hypot(opponent["x"] - me["x"], opponent["y"] - me["y"])
        if distance_to_opponent < 32:
            target_x, target_y = opponent["x"], opponent["y"]
        else:
            own_goal_y = 0.0 if player_id == "player_1" else field["height"]
            target_x = (opponent["x"] + field["width"] / 2) / 2
            target_y = (opponent["y"] + own_goal_y) / 2
    else:
        target_x, target_y = ball["x"], ball["y"]
        if ball["status"] == "moving":
            velocity = ball.get("velocity", {})
            target_x += float(velocity.get("x", 0.0))
            target_y += float(velocity.get("y", 0.0))
    preferred = direction_toward(target_x - me["x"], target_y - me["y"], dead_zone=0.6)
    return {"move": _safe_move(observation, preferred)}


class QLearningBot:
    """Small tabular policy intended as a clear training example, not a state-of-the-art bot."""

    def __init__(self, q_table: dict[str, list[float]] | None = None, seed: int = 0):
        self.q_table = q_table or {}
        self.random = random.Random(seed)
        self.actions = MOVES

    @staticmethod
    def state_key(observation: dict[str, Any]) -> str:
        player_id = observation["player_id"]
        opponent_id = observation["opponent_id"]
        state = observation["state"]
        me = state["players"][player_id]
        opponent = state["players"][opponent_id]
        ball = state["ball"]
        width = state["field"]["width"]
        height = state["field"]["height"]

        def bucket(value: float, scale: float) -> int:
            normalized = max(-1.0, min(1.0, value / scale))
            return int(round(normalized * 2))

        possession = "self" if ball["possession"] == player_id else (
            "opponent" if ball["possession"] == opponent_id else "free"
        )
        values = (
            bucket(ball["x"] - me["x"], width),
            bucket(ball["y"] - me["y"], height),
            bucket(opponent["x"] - me["x"], width),
            bucket(opponent["y"] - me["y"], height),
            possession,
        )
        return "|".join(map(str, values))

    def choose_index(self, observation: dict[str, Any], epsilon: float = 0.0) -> int:
        key = self.state_key(observation)
        values = self.q_table.setdefault(key, [0.0] * len(self.actions))
        if self.random.random() < epsilon:
            return self.random.randrange(len(self.actions))
        if max(values) - min(values) < 1e-6:
            # Unseen states used to select index zero (STAY), making an
            # untrained or sparse model freeze. Use the tactical baseline.
            return self.actions.index(practice_action(observation)["move"])
        best = max(values)
        return next(index for index, value in enumerate(values) if value == best)

    def action_from_index(self, observation: dict[str, Any], index: int) -> dict[str, Any]:
        move = self.actions[index]
        action: dict[str, Any] = {"move": move}
        if observation["state"]["ball"]["possession"] == observation["player_id"]:
            tactical = practice_action(observation)
            if "kick" in tactical:
                action["kick"] = tactical["kick"]
        return action

    def decide(self, observation: dict[str, Any]) -> dict[str, Any]:
        return self.action_from_index(observation, self.choose_index(observation))

    def update(
        self,
        observation: dict[str, Any],
        action_index: int,
        reward: float,
        next_observation: dict[str, Any],
        done: bool,
        learning_rate: float,
        discount: float,
    ) -> None:
        key = self.state_key(observation)
        next_key = self.state_key(next_observation)
        values = self.q_table.setdefault(key, [0.0] * len(self.actions))
        next_values = self.q_table.setdefault(next_key, [0.0] * len(self.actions))
        target = reward if done else reward + discount * max(next_values)
        values[action_index] += learning_rate * (target - values[action_index])

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps({"format": 1, "actions": self.actions, "q_table": self.q_table}, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path, seed: int = 0) -> "QLearningBot":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if raw.get("actions") != MOVES:
            raise ValueError("Model action list does not match this environment")
        return cls(q_table=raw["q_table"], seed=seed)


def shaped_reward(
    player_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
    events: list[dict[str, Any]],
) -> float:
    opponent = "player_2" if player_id == "player_1" else "player_1"
    reward = 0.0
    for event in events:
        if event["type"] == "goal":
            reward += 10.0 if event["scorer"] == player_id else -10.0
        elif event["type"] == "kick" and event["player"] == player_id:
            reward += 0.05
        elif event["type"] == "tackle":
            reward += 0.4 if event["player"] == player_id else -0.4
        elif event["type"] == "possession_timeout" and event["player"] == player_id:
            reward -= 0.5
    before_owner = before["ball"]["possession"]
    after_owner = after["ball"]["possession"]
    if after_owner == player_id:
        reward += 0.2 if before_owner != player_id else 0.005
    direction = 1.0 if player_id == "player_1" else -1.0
    progress = direction * (after["ball"]["y"] - before["ball"]["y"])
    reward += 0.002 * max(-5.0, min(5.0, progress))
    if after_owner == opponent:
        reward -= 0.08 if before_owner != opponent else 0.005

    before_me = before["players"][player_id]
    after_me = after["players"][player_id]
    before_distance = math.hypot(before["ball"]["x"] - before_me["x"], before["ball"]["y"] - before_me["y"])
    after_distance = math.hypot(after["ball"]["x"] - after_me["x"], after["ball"]["y"] - after_me["y"])
    if before_owner != player_id:
        reward += 0.003 * max(-5.0, min(5.0, before_distance - after_distance))
    return reward

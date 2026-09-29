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


def practice_action(observation: dict[str, Any]) -> dict[str, Any]:
    """Deterministic baseline: chase the ball, then shoot toward the opponent goal."""
    player_id = observation["player_id"]
    state = observation["state"]
    me = state["players"][player_id]
    ball = state["ball"]
    if ball["possession"] == player_id:
        attack = observation["attack_direction"]
        return {
            "move": attack,
            "kick": {"direction": attack, "power": max(observation["action_space"]["kick"]["power"])},
        }
    return {"move": direction_toward(ball["x"] - me["x"], ball["y"] - me["y"])}


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
        best = max(values)
        return next(index for index, value in enumerate(values) if value == best)

    def action_from_index(self, observation: dict[str, Any], index: int) -> dict[str, Any]:
        move = self.actions[index]
        action: dict[str, Any] = {"move": move}
        if observation["state"]["ball"]["possession"] == observation["player_id"]:
            attack = observation["attack_direction"]
            # Shoot mostly forward, but movement choice still controls positioning between kicks.
            action["kick"] = {
                "direction": attack,
                "power": max(observation["action_space"]["kick"]["power"]),
            }
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
            reward += 1.0 if event["scorer"] == player_id else -1.0
    if after["ball"]["possession"] == player_id:
        reward += 0.01
    direction = 1.0 if player_id == "player_1" else -1.0
    progress = direction * (after["ball"]["y"] - before["ball"]["y"])
    reward += 0.002 * max(-5.0, min(5.0, progress))
    if after["ball"]["possession"] == opponent:
        reward -= 0.005
    return reward

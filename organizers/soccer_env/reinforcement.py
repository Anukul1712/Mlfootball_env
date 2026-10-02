from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

from .bots import DIRECTION_VECTORS, MOVES, practice_action


KICK_DIRECTIONS = [name for name in MOVES if name != "STAY"]
ACTION_COUNT = len(MOVES) + len(KICK_DIRECTIONS) * 3


def _bucket(value: float, limits: tuple[float, ...]) -> int:
    return next((index for index, limit in enumerate(limits) if value < limit), len(limits))


def _sector(dx: float, dy: float) -> int:
    if abs(dx) + abs(dy) < 1e-9:
        return 8
    return int(round(math.atan2(dy, dx) / (math.pi / 4))) % 8


class ReinforcementPolicy:
    """Tabular Q-learning policy that learns movement, dribbling, and shooting.

    The state is normalized into the player's attacking perspective. Unlike
    the original example learner, kick direction and power are learned actions
    rather than hard-coded tactical decisions.
    """

    def __init__(
        self,
        q_table: dict[str, list[float]] | None = None,
        visits: dict[str, int] | None = None,
        seed: int = 0,
        evaluation_epsilon: float = 0.05,
        safety_margin: float = 0.6,
    ) -> None:
        self.q_table = q_table or {}
        self.visits = visits or {}
        self.model_seed = int(seed)
        self.evaluation_epsilon = float(evaluation_epsilon)
        self.safety_margin = float(safety_margin)
        self.random = random.Random(seed)
        self._match_seeded = False

    @staticmethod
    def state_key(observation: dict[str, Any]) -> str:
        player_id = observation["player_id"]
        opponent_id = observation["opponent_id"]
        state = observation["state"]
        field = state["field"]
        me = state["players"][player_id]
        opponent = state["players"][opponent_id]
        ball = state["ball"]
        width, height = float(field["width"]), float(field["height"])
        sign = 1.0 if observation["attack_direction"] == "UP" else -1.0
        attack_y = me["y"] if sign > 0 else height - me["y"]

        ball_dx = ball["x"] - me["x"]
        ball_dy = sign * (ball["y"] - me["y"])
        opponent_dx = opponent["x"] - me["x"]
        opponent_dy = sign * (opponent["y"] - me["y"])
        velocity = ball.get("velocity", {})
        velocity_x = float(velocity.get("x", 0.0))
        velocity_y = sign * float(velocity.get("y", 0.0))

        possession = (
            "S" if ball["possession"] == player_id
            else "O" if ball["possession"] == opponent_id
            else "F"
        )
        nearest_obstacle = (999.0, 8)
        for obstacle in state.get("obstacles", []):
            center_x = obstacle["x"] + obstacle["width"] / 2
            center_y = obstacle["y"] + obstacle["height"] / 2
            dx = center_x - me["x"]
            dy = sign * (center_y - me["y"])
            distance = math.hypot(dx, dy)
            if distance < nearest_obstacle[0]:
                nearest_obstacle = (distance, _sector(dx, dy))

        values = (
            min(4, int(me["x"] / width * 5)),
            min(6, int(attack_y / height * 7)),
            _sector(ball_dx, ball_dy),
            _bucket(math.hypot(ball_dx, ball_dy), (7, 16, 32, 60)),
            _sector(opponent_dx, opponent_dy),
            _bucket(math.hypot(opponent_dx, opponent_dy), (8, 18, 38, 70)),
            possession,
            ball["status"][0].upper(),
            _sector(velocity_x, velocity_y),
            _bucket(float(ball.get("remaining_kick_distance", 0.0)), (1, 25, 60)),
            _bucket(int(ball.get("possession_steps", 0)), (1, 3, 6)),
            nearest_obstacle[1] if nearest_obstacle[0] < 24 else 8,
            _bucket(nearest_obstacle[0], (8, 16, 24)),
        )
        return "|".join(map(str, values))

    @staticmethod
    def valid_indices(observation: dict[str, Any]) -> list[int]:
        # STAY is excluded from exploration so an untrained state remains active.
        moves = list(range(1, len(MOVES)))
        ball = observation["state"]["ball"]
        if ball["possession"] == observation["player_id"]:
            # Control newly won possession before shooting. Once a kick is
            # available, mask lateral/backward clearances so the learner cannot
            # repeatedly throw kickoffs away toward a touchline.
            attack = observation["attack_direction"]
            forward_directions = [attack, f"{attack}_LEFT", f"{attack}_RIGHT"]
            if int(ball.get("possession_steps", 0)) < 2:
                return [MOVES.index(direction) for direction in forward_directions]
            kicks = [
                len(MOVES) + KICK_DIRECTIONS.index(direction) * 3 + power_offset
                for direction in forward_directions
                for power_offset in range(3)
            ]
            return moves + kicks
        return moves

    @staticmethod
    def action_from_index(observation: dict[str, Any], index: int) -> dict[str, Any]:
        if index < len(MOVES):
            return {"move": MOVES[index]}
        kick_index = index - len(MOVES)
        direction = KICK_DIRECTIONS[kick_index // 3]
        power = kick_index % 3 + 1
        return {"move": direction, "kick": {"direction": direction, "power": power}}

    @staticmethod
    def index_from_action(action: dict[str, Any]) -> int:
        kick = action.get("kick")
        if isinstance(kick, dict) and kick.get("direction") in KICK_DIRECTIONS:
            power = max(1, min(3, int(kick.get("power", 1))))
            return len(MOVES) + KICK_DIRECTIONS.index(kick["direction"]) * 3 + power - 1
        return MOVES.index(action.get("move", "STAY"))

    def choose_index(
        self,
        observation: dict[str, Any],
        epsilon: float,
        use_safety_guard: bool = False,
    ) -> int:
        key = self.state_key(observation)
        valid = self.valid_indices(observation)
        values = self.q_table.get(key)
        if self.random.random() < epsilon:
            return self.random.choice(valid)
        if values is None or self.visits.get(key, 0) < 2:
            fallback = self.index_from_action(practice_action(observation))
            return fallback if fallback in valid else self.random.choice(valid)
        best = max(values[index] for index in valid)
        if use_safety_guard:
            fallback = self.index_from_action(practice_action(observation))
            if fallback in valid and best - values[fallback] < self.safety_margin:
                return fallback
        choices = [index for index in valid if abs(values[index] - best) < 1e-9]
        return self.random.choice(choices)

    def decide(self, observation: dict[str, Any]) -> dict[str, Any]:
        if not self._match_seeded:
            state_seed = int(observation["state"].get("seed", 0))
            side_seed = 17 if observation["player_id"] == "player_1" else 31
            self.random.seed(self.model_seed ^ (state_seed * 1_000_003) ^ side_seed)
            self._match_seeded = True
        index = self.choose_index(
            observation,
            self.evaluation_epsilon,
            use_safety_guard=True,
        )
        return self.action_from_index(observation, index)

    def update(
        self,
        observation: dict[str, Any],
        action_index: int,
        reward: float,
        next_observation: dict[str, Any],
        done: bool,
        learning_rate: float = 0.14,
        discount: float = 0.97,
    ) -> None:
        key = self.state_key(observation)
        values = self.q_table.setdefault(key, [0.0] * ACTION_COUNT)
        self.visits[key] = self.visits.get(key, 0) + 1
        if done:
            target = reward
        else:
            next_key = self.state_key(next_observation)
            next_values = self.q_table.setdefault(next_key, [0.0] * ACTION_COUNT)
            next_valid = self.valid_indices(next_observation)
            target = reward + discount * max(next_values[index] for index in next_valid)
        values[action_index] += learning_rate * (target - values[action_index])

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        sparse_table: dict[str, dict[str, float]] = {}
        retained_visits: dict[str, int] = {}
        for key, values in self.q_table.items():
            visits = self.visits.get(key, 0)
            if visits < 2:
                continue
            learned = {
                str(index): round(value, 6)
                for index, value in enumerate(values)
                if abs(value) >= 1e-6
            }
            if learned:
                sparse_table[key] = learned
                retained_visits[key] = visits
        path.write_text(
            json.dumps(
                {
                    "format": 3,
                    "algorithm": "tabular_q_learning_full_action_space",
                    "action_count": ACTION_COUNT,
                    "seed": self.model_seed,
                    "evaluation_epsilon": self.evaluation_epsilon,
                    "safety_margin": self.safety_margin,
                    "q_table": sparse_table,
                    "visits": retained_visits,
                },
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "ReinforcementPolicy":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if raw.get("format") not in {2, 3} or raw.get("action_count") != ACTION_COUNT:
            raise ValueError("Unsupported reinforcement policy format")
        if raw["format"] == 3:
            q_table: dict[str, list[float]] = {}
            for key, sparse_values in raw["q_table"].items():
                values = [0.0] * ACTION_COUNT
                for index, value in sparse_values.items():
                    values[int(index)] = float(value)
                q_table[key] = values
        else:
            q_table = raw["q_table"]
        return cls(
            q_table=q_table,
            visits={key: int(value) for key, value in raw.get("visits", {}).items()},
            seed=int(raw.get("seed", 0)),
            evaluation_epsilon=float(raw.get("evaluation_epsilon", 0.05)),
            safety_margin=float(raw.get("safety_margin", 0.6)),
        )


def reinforcement_reward(
    player_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
    events: list[dict[str, Any]],
    action: dict[str, Any],
) -> float:
    opponent_id = "player_2" if player_id == "player_1" else "player_1"
    sign = 1.0 if player_id == "player_1" else -1.0
    reward = -0.002
    for event in events:
        event_type = event.get("type")
        if event_type == "goal":
            reward += 25.0 if event.get("scorer") == player_id else -25.0
        elif event_type in {"interception", "tackle", "possession"}:
            reward += 0.8 if event.get("player") == player_id else -0.6
        elif event_type == "kick" and event.get("player") == player_id:
            reward += 0.08
        elif event_type == "possession_timeout" and event.get("player") == player_id:
            reward -= 1.0

    before_owner = before["ball"]["possession"]
    after_owner = after["ball"]["possession"]
    if before_owner != player_id and after_owner == player_id:
        reward += 0.6
    if before_owner == player_id and after_owner == opponent_id:
        reward -= 0.8

    progress = sign * (after["ball"]["y"] - before["ball"]["y"])
    reward += 0.012 * max(-8.0, min(8.0, progress))

    before_me = before["players"][player_id]
    after_me = after["players"][player_id]
    before_distance = math.hypot(
        before["ball"]["x"] - before_me["x"], before["ball"]["y"] - before_me["y"]
    )
    after_distance = math.hypot(
        after["ball"]["x"] - after_me["x"], after["ball"]["y"] - after_me["y"]
    )
    if before_owner != player_id:
        reward += 0.006 * max(-8.0, min(8.0, before_distance - after_distance))
    if action.get("move") == "STAY":
        reward -= 0.04
    kick = action.get("kick")
    if isinstance(kick, dict):
        kick_vector = DIRECTION_VECTORS.get(str(kick.get("direction")), (0, 0))
        if sign * kick_vector[1] <= 0:
            reward -= 1.5
    return reward

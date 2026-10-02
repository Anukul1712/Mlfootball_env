from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GameConfig:
    field_width: float = 100.0
    field_height: float = 140.0
    goal_width: float = 32.0
    player_radius: float = 3.0
    player_speed: float = 4.0
    ball_radius: float = 1.5
    ball_speed: float = 7.0
    possession_radius: float = 5.0
    kick_distances: tuple[float, ...] = (28.0, 55.0, 85.0)
    obstacle_count: int = 6
    obstacle_width: float = 12.0
    obstacle_height: float = 8.0
    maximum_iterations: int = 300
    maximum_goals: int = 5
    possession_limit_iterations: int = 10
    loose_ball_restart_iterations: int = 20
    initial_possessor: str = "player_1"

    @classmethod
    def from_json(cls, path: str | Path) -> "GameConfig":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if "kick_distances" in raw:
            raw["kick_distances"] = tuple(float(value) for value in raw["kick_distances"])
        config = cls(**raw)
        config.validate()
        return config

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["kick_distances"] = list(self.kick_distances)
        return value

    def validate(self) -> None:
        positive = {
            "field_width": self.field_width,
            "field_height": self.field_height,
            "goal_width": self.goal_width,
            "player_radius": self.player_radius,
            "player_speed": self.player_speed,
            "ball_radius": self.ball_radius,
            "ball_speed": self.ball_speed,
            "possession_radius": self.possession_radius,
            "obstacle_width": self.obstacle_width,
            "obstacle_height": self.obstacle_height,
            "maximum_iterations": self.maximum_iterations,
            "maximum_goals": self.maximum_goals,
            "possession_limit_iterations": self.possession_limit_iterations,
            "loose_ball_restart_iterations": self.loose_ball_restart_iterations,
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.goal_width >= self.field_width:
            raise ValueError("goal_width must be smaller than field_width")
        if self.obstacle_count < 0 or self.obstacle_count % 2:
            raise ValueError("obstacle_count must be a non-negative even number")
        if not self.kick_distances or any(value <= 0 for value in self.kick_distances):
            raise ValueError("kick_distances must contain positive distances")
        if self.initial_possessor not in {"player_1", "player_2"}:
            raise ValueError("initial_possessor must be player_1 or player_2")

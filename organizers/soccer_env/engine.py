from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass
from typing import Any

from .config import GameConfig


DIRECTIONS: dict[str, tuple[float, float]] = {
    "STAY": (0.0, 0.0),
    "UP": (0.0, 1.0),
    "UP_RIGHT": (1.0, 1.0),
    "RIGHT": (1.0, 0.0),
    "DOWN_RIGHT": (1.0, -1.0),
    "DOWN": (0.0, -1.0),
    "DOWN_LEFT": (-1.0, -1.0),
    "LEFT": (-1.0, 0.0),
    "UP_LEFT": (-1.0, 1.0),
}
PLAYERS = ("player_1", "player_2")


def _unit(vector: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(*vector)
    return (0.0, 0.0) if length == 0 else (vector[0] / length, vector[1] / length)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


@dataclass
class Rectangle:
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


class SoccerEnv:
    """A dependency-free, deterministic environment following rough game rules.pdf.

    Coordinate system: (0, 0) is the bottom-left. Player 1 defends the
    bottom goal and attacks upward. Player 2 defends the top goal and attacks
    downward.
    """

    def __init__(self, config: GameConfig | None = None):
        self.config = config or GameConfig()
        self.config.validate()
        self.seed = 0
        self.iteration = 0
        self.players: dict[str, tuple[float, float]] = {}
        self.ball_position = (0.0, 0.0)
        self.ball_velocity = (0.0, 0.0)
        self.ball_remaining_distance = 0.0
        self.possession: str | None = None
        self.last_touch: str | None = None
        self.score = {"player_1": 0, "player_2": 0}
        self.obstacles: list[Rectangle] = []
        self.done = False
        self.termination_reason: str | None = None
        self.events: list[dict[str, Any]] = []

    def reset(self, seed: int = 0) -> dict[str, dict[str, Any]]:
        self.seed = int(seed)
        self.iteration = 0
        self.score = {"player_1": 0, "player_2": 0}
        self.done = False
        self.termination_reason = None
        self.events = []
        self.obstacles = self._generate_obstacles(random.Random(self.seed))
        self._restart(self.config.initial_possessor)
        return self.observations()

    def observations(self) -> dict[str, dict[str, Any]]:
        state = self.state()
        return {
            player: {
                "player_id": player,
                "opponent_id": "player_2" if player == "player_1" else "player_1",
                "attack_direction": "UP" if player == "player_1" else "DOWN",
                "state": copy.deepcopy(state),
                "action_space": {
                    "move": list(DIRECTIONS),
                    "kick": {
                        "allowed_only_with_possession": True,
                        "direction": [name for name in DIRECTIONS if name != "STAY"],
                        "power": list(range(1, len(self.config.kick_distances) + 1)),
                    },
                },
            }
            for player in PLAYERS
        }

    def state(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "iteration": self.iteration,
            "maximum_iterations": self.config.maximum_iterations,
            "field": {
                "width": self.config.field_width,
                "height": self.config.field_height,
                "goal_width": self.config.goal_width,
                "player_1_own_goal": "bottom",
                "player_2_own_goal": "top",
            },
            "players": {
                name: {"x": position[0], "y": position[1]}
                for name, position in self.players.items()
            },
            "ball": {
                "x": self.ball_position[0],
                "y": self.ball_position[1],
                "status": "possessed" if self.possession else (
                    "moving" if self.ball_remaining_distance > 0 else "stationary"
                ),
                "possession": self.possession,
                "velocity": {"x": self.ball_velocity[0], "y": self.ball_velocity[1]},
                "remaining_kick_distance": self.ball_remaining_distance,
            },
            "obstacles": [obstacle.to_dict() for obstacle in self.obstacles],
            "score": dict(self.score),
            "done": self.done,
            "termination_reason": self.termination_reason,
        }

    def step(
        self,
        player_1_action: dict[str, Any] | None,
        player_2_action: dict[str, Any] | None,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        if self.done:
            raise RuntimeError("The match is over. Call reset() before stepping again.")

        actions = {
            "player_1": self.normalize_action(player_1_action),
            "player_2": self.normalize_action(player_2_action),
        }
        self.events = []
        self._move_players(actions)

        if self.possession:
            self.ball_position = self.players[self.possession]
            kick = actions[self.possession].get("kick")
            if kick:
                self._start_kick(self.possession, kick)

        scorer = self._move_ball() if self.possession is None else None
        if scorer:
            self.score[scorer] += 1
            conceder = "player_2" if scorer == "player_1" else "player_1"
            self.events.append({"type": "goal", "scorer": scorer, "score": dict(self.score)})
        else:
            self._claim_stationary_ball()

        self.iteration += 1
        if sum(self.score.values()) >= self.config.maximum_goals:
            self.done = True
            self.termination_reason = "maximum_goals"
        elif self.iteration >= self.config.maximum_iterations:
            self.done = True
            self.termination_reason = "maximum_iterations"

        if scorer and not self.done:
            self._restart(conceder)
            self.events.append({"type": "restart", "possession": conceder})

        info = {
            "actions_applied": actions,
            "events": copy.deepcopy(self.events),
            "done": self.done,
            "result": self.result() if self.done else None,
        }
        return self.observations(), info

    def normalize_action(self, action: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(action, dict):
            return {"move": "STAY"}
        move = str(action.get("move", "STAY")).upper()
        if move not in DIRECTIONS:
            move = "STAY"
        normalized: dict[str, Any] = {"move": move}
        kick = action.get("kick")
        if isinstance(kick, dict):
            direction = str(kick.get("direction", "")).upper()
            try:
                power = int(kick.get("power", 0))
            except (TypeError, ValueError):
                power = 0
            if direction in DIRECTIONS and direction != "STAY" and 1 <= power <= len(self.config.kick_distances):
                normalized["kick"] = {"direction": direction, "power": power}
        return normalized

    def result(self) -> dict[str, Any]:
        if self.score["player_1"] > self.score["player_2"]:
            winner = "player_1"
        elif self.score["player_2"] > self.score["player_1"]:
            winner = "player_2"
        else:
            winner = None
        return {
            "winner": winner,
            "draw": winner is None,
            "score": dict(self.score),
            "iterations": self.iteration,
            "termination_reason": self.termination_reason,
            "seed": self.seed,
        }

    def _starting_positions(self) -> dict[str, tuple[float, float]]:
        return {
            "player_1": (self.config.field_width / 2, self.config.field_height * 0.25),
            "player_2": (self.config.field_width / 2, self.config.field_height * 0.75),
        }

    def _restart(self, possessor: str) -> None:
        self.players = self._starting_positions()
        self.possession = possessor
        self.ball_position = self.players[possessor]
        self.ball_velocity = (0.0, 0.0)
        self.ball_remaining_distance = 0.0
        self.last_touch = possessor

    def _move_players(self, actions: dict[str, dict[str, Any]]) -> None:
        old = dict(self.players)
        proposed: dict[str, tuple[float, float]] = {}
        for player in PLAYERS:
            direction = _unit(DIRECTIONS[actions[player]["move"]])
            candidate = (
                old[player][0] + direction[0] * self.config.player_speed,
                old[player][1] + direction[1] * self.config.player_speed,
            )
            proposed[player] = candidate if self._valid_player_position(candidate) else old[player]

        if _distance(proposed["player_1"], proposed["player_2"]) < 2 * self.config.player_radius:
            proposed = old
            self.events.append({"type": "player_collision", "resolution": "both_movements_cancelled"})
        self.players = proposed

    def _valid_player_position(self, position: tuple[float, float]) -> bool:
        radius = self.config.player_radius
        x, y = position
        if x - radius < 0 or x + radius > self.config.field_width:
            return False
        if y - radius < 0 or y + radius > self.config.field_height:
            return False
        return not any(self._circle_hits_rectangle(position, radius, obstacle) for obstacle in self.obstacles)

    def _start_kick(self, player: str, kick: dict[str, Any]) -> None:
        direction = _unit(DIRECTIONS[kick["direction"]])
        clearance = self.config.player_radius + self.config.ball_radius + 0.05
        origin = self.players[player]
        self.ball_position = (origin[0] + direction[0] * clearance, origin[1] + direction[1] * clearance)
        self.ball_velocity = (direction[0] * self.config.ball_speed, direction[1] * self.config.ball_speed)
        self.ball_remaining_distance = self.config.kick_distances[kick["power"] - 1]
        self.possession = None
        self.last_touch = player
        self.events.append({"type": "kick", "player": player, **kick})

    def _move_ball(self) -> str | None:
        if self.ball_remaining_distance <= 0 or self.ball_velocity == (0.0, 0.0):
            return None

        travel = min(self.config.ball_speed, self.ball_remaining_distance)
        substep_limit = max(0.25, self.config.ball_radius * 0.45)
        substeps = max(1, math.ceil(travel / substep_limit))
        step_distance = travel / substeps

        for _ in range(substeps):
            velocity_unit = _unit(self.ball_velocity)
            previous = self.ball_position
            candidate = (
                previous[0] + velocity_unit[0] * step_distance,
                previous[1] + velocity_unit[1] * step_distance,
            )

            scorer = self._goal_scorer(candidate)
            if scorer:
                self.ball_position = candidate
                self.ball_remaining_distance = 0.0
                self.ball_velocity = (0.0, 0.0)
                return scorer

            candidate = self._bounce_from_walls(candidate)
            candidate = self._bounce_from_obstacles(previous, candidate)
            self.ball_position = candidate
            self.ball_remaining_distance = max(0.0, self.ball_remaining_distance - step_distance)

            for player in PLAYERS:
                if _distance(self.ball_position, self.players[player]) <= self.config.ball_radius + self.config.player_radius:
                    self.possession = player
                    self.last_touch = player
                    self.ball_position = self.players[player]
                    self.ball_velocity = (0.0, 0.0)
                    self.ball_remaining_distance = 0.0
                    self.events.append({"type": "interception", "player": player})
                    return None

        if self.ball_remaining_distance <= 1e-9:
            self.ball_remaining_distance = 0.0
            self.ball_velocity = (0.0, 0.0)
            self.events.append({"type": "ball_stopped"})
        return None

    def _goal_scorer(self, candidate: tuple[float, float]) -> str | None:
        goal_left = (self.config.field_width - self.config.goal_width) / 2
        goal_right = goal_left + self.config.goal_width
        inside_mouth = goal_left <= candidate[0] <= goal_right
        if inside_mouth and candidate[1] + self.config.ball_radius >= self.config.field_height:
            return "player_1"
        if inside_mouth and candidate[1] - self.config.ball_radius <= 0:
            return "player_2"
        return None

    def _bounce_from_walls(self, candidate: tuple[float, float]) -> tuple[float, float]:
        x, y = candidate
        vx, vy = self.ball_velocity
        radius = self.config.ball_radius
        bounced = []
        if x - radius < 0 or x + radius > self.config.field_width:
            vx = -vx
            x = min(max(x, radius), self.config.field_width - radius)
            bounced.append("vertical_wall")
        if y - radius < 0 or y + radius > self.config.field_height:
            vy = -vy
            y = min(max(y, radius), self.config.field_height - radius)
            bounced.append("horizontal_wall")
        if bounced:
            self.ball_velocity = (vx, vy)
            self.events.append({"type": "bounce", "surface": "+".join(bounced)})
        return (x, y)

    def _bounce_from_obstacles(
        self, previous: tuple[float, float], candidate: tuple[float, float]
    ) -> tuple[float, float]:
        radius = self.config.ball_radius
        for obstacle in self.obstacles:
            if not self._circle_hits_rectangle(candidate, radius, obstacle):
                continue
            left = obstacle.x - radius
            right = obstacle.x + obstacle.width + radius
            bottom = obstacle.y - radius
            top = obstacle.y + obstacle.height + radius
            crossed_x = previous[0] <= left or previous[0] >= right
            crossed_y = previous[1] <= bottom or previous[1] >= top
            vx, vy = self.ball_velocity
            if crossed_x:
                vx = -vx
            if crossed_y:
                vy = -vy
            if not crossed_x and not crossed_y:
                vx, vy = -vx, -vy
            self.ball_velocity = (vx, vy)
            self.events.append({"type": "bounce", "surface": "obstacle"})
            direction = _unit(self.ball_velocity)
            return (
                previous[0] + direction[0] * min(0.05, radius / 10),
                previous[1] + direction[1] * min(0.05, radius / 10),
            )
        return candidate

    def _claim_stationary_ball(self) -> None:
        if self.possession is not None or self.ball_remaining_distance > 0:
            return
        candidates = [
            (_distance(self.players[player], self.ball_position), player)
            for player in PLAYERS
            if _distance(self.players[player], self.ball_position) <= self.config.possession_radius
        ]
        if candidates:
            _, winner = min(candidates, key=lambda item: (item[0], item[1]))
            self.possession = winner
            self.last_touch = winner
            self.ball_position = self.players[winner]
            self.events.append({"type": "possession", "player": winner})

    @staticmethod
    def _circle_hits_rectangle(
        center: tuple[float, float], radius: float, rectangle: Rectangle
    ) -> bool:
        closest_x = min(max(center[0], rectangle.x), rectangle.x + rectangle.width)
        closest_y = min(max(center[1], rectangle.y), rectangle.y + rectangle.height)
        return _distance(center, (closest_x, closest_y)) < radius

    def _generate_obstacles(self, rng: random.Random) -> list[Rectangle]:
        if self.config.obstacle_count == 0:
            return []
        obstacles: list[Rectangle] = []
        starts = list(self._starting_positions().values())
        starts.append((self.config.field_width / 2, self.config.field_height / 2))
        half_count = self.config.obstacle_count // 2
        margin = self.config.player_radius + self.config.player_speed + 1

        for _ in range(half_count):
            for _attempt in range(10_000):
                x = rng.uniform(margin, self.config.field_width - self.config.obstacle_width - margin)
                y = rng.uniform(
                    margin,
                    self.config.field_height / 2 - self.config.obstacle_height - margin,
                )
                lower = Rectangle(x, y, self.config.obstacle_width, self.config.obstacle_height)
                upper = Rectangle(
                    x,
                    self.config.field_height - y - self.config.obstacle_height,
                    self.config.obstacle_width,
                    self.config.obstacle_height,
                )
                pair = [lower, upper]
                if any(
                    self._circle_hits_rectangle(point, self.config.possession_radius + margin, rectangle)
                    for point in starts
                    for rectangle in pair
                ):
                    continue
                if any(self._rectangles_overlap(rectangle, existing, padding=2.0) for rectangle in pair for existing in obstacles):
                    continue
                obstacles.extend(pair)
                break
            else:
                raise RuntimeError("Could not generate a valid obstacle layout; reduce obstacle size/count")
        return obstacles

    @staticmethod
    def _rectangles_overlap(a: Rectangle, b: Rectangle, padding: float = 0.0) -> bool:
        return not (
            a.x + a.width + padding <= b.x
            or b.x + b.width + padding <= a.x
            or a.y + a.height + padding <= b.y
            or b.y + b.height + padding <= a.y
        )

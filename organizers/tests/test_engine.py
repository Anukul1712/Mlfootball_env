from __future__ import annotations

import json
import unittest

from soccer_env import GameConfig, SoccerEnv
from soccer_env.engine import DIRECTIONS


class SoccerEnvironmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = GameConfig(
            obstacle_count=0,
            maximum_iterations=30,
            maximum_goals=3,
        )

    def test_same_seed_and_actions_reproduce_state(self) -> None:
        config = GameConfig(obstacle_count=6, maximum_iterations=20)
        first, second = SoccerEnv(config), SoccerEnv(config)
        first.reset(1234)
        second.reset(1234)
        actions = [
            ({"move": "UP", "kick": {"direction": "UP", "power": 2}}, {"move": "LEFT"}),
            ({"move": "RIGHT"}, {"move": "DOWN_LEFT"}),
            ({"move": "STAY"}, {"move": "DOWN"}),
        ]
        for player_1_action, player_2_action in actions:
            first.step(player_1_action, player_2_action)
            second.step(player_1_action, player_2_action)
        self.assertEqual(json.dumps(first.state(), sort_keys=True), json.dumps(second.state(), sort_keys=True))

    def test_obstacles_are_mirrored(self) -> None:
        env = SoccerEnv(GameConfig(obstacle_count=6))
        env.reset(44)
        rectangles = {(round(item.x, 8), round(item.y, 8)) for item in env.obstacles}
        for obstacle in env.obstacles:
            mirrored_y = env.config.field_height - obstacle.y - obstacle.height
            self.assertIn((round(obstacle.x, 8), round(mirrored_y, 8)), rectangles)

    def test_diagonal_speed_is_normalized(self) -> None:
        env = SoccerEnv(self.config)
        env.reset(1)
        before = env.players["player_1"]
        env.step({"move": "UP_RIGHT"}, {"move": "STAY"})
        after = env.players["player_1"]
        travelled = ((after[0] - before[0]) ** 2 + (after[1] - before[1]) ** 2) ** 0.5
        self.assertAlmostEqual(travelled, self.config.player_speed)

    def test_kick_releases_ball_and_moves_it(self) -> None:
        env = SoccerEnv(self.config)
        env.reset(2)
        old_y = env.ball_position[1]
        env.step({"move": "STAY", "kick": {"direction": "UP", "power": 1}}, {"move": "STAY"})
        self.assertIsNone(env.possession)
        self.assertGreater(env.ball_position[1], old_y)
        self.assertGreater(env.ball_remaining_distance, 0)

    def test_goal_updates_score_and_gives_conceder_restart(self) -> None:
        env = SoccerEnv(self.config)
        env.reset(3)
        env.possession = None
        env.ball_position = (self.config.field_width / 2, self.config.field_height - 2)
        env.ball_velocity = (0.0, self.config.ball_speed)
        env.ball_remaining_distance = 10
        env.step({"move": "STAY"}, {"move": "STAY"})
        self.assertEqual(env.score["player_1"], 1)
        self.assertEqual(env.possession, "player_2")
        self.assertEqual(env.ball_position, env.players["player_2"])

    def test_invalid_action_becomes_safe_stay(self) -> None:
        env = SoccerEnv(self.config)
        env.reset(4)
        before = env.players["player_1"]
        env.step({"move": "TELEPORT", "kick": {"direction": "SIDEWAYS", "power": 99}}, None)
        self.assertEqual(env.players["player_1"], before)

    def test_both_observations_share_current_locations(self) -> None:
        env = SoccerEnv(self.config)
        observations = env.reset(5)
        p1_state = observations["player_1"]["state"]
        p2_state = observations["player_2"]["state"]
        self.assertEqual(p1_state["players"], p2_state["players"])
        self.assertEqual(p1_state["ball"], p2_state["ball"])
        self.assertEqual(set(DIRECTIONS), set(observations["player_1"]["action_space"]["move"]))


if __name__ == "__main__":
    unittest.main()

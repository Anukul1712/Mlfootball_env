from __future__ import annotations

import json
import unittest

from soccer_env import GameConfig, SoccerEnv
from soccer_env.engine import DIRECTIONS
from soccer_env.bots import QLearningBot, aggressive_action, counter_action, practice_action
from soccer_env.reinforcement import ACTION_COUNT, ReinforcementPolicy, reinforcement_reward


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

    def test_contact_does_not_cancel_both_players_forever(self) -> None:
        env = SoccerEnv(self.config)
        observations = env.reset(6)
        for _ in range(12):
            observations, _ = env.step(
                practice_action(observations["player_1"]),
                practice_action(observations["player_2"]),
            )
        self.assertGreater(env.iteration, 0)
        self.assertTrue(env.ball_position != self._starting_ball(env) or env.possession is not None)

    @staticmethod
    def _starting_ball(env: SoccerEnv) -> tuple[float, float]:
        return (env.config.field_width / 2, env.config.field_height * 0.25)

    def test_idle_possessor_is_forced_to_release_ball(self) -> None:
        config = GameConfig(obstacle_count=0, maximum_iterations=30, possession_limit_iterations=3)
        env = SoccerEnv(config)
        env.reset(7)
        events = []
        for _ in range(3):
            _, info = env.step({"move": "STAY"}, {"move": "STAY"})
            events.extend(info["events"])
        self.assertTrue(any(event["type"] == "possession_timeout" for event in events))
        self.assertIsNone(env.possession)

    def test_stalled_loose_ball_gets_a_midfield_drop_ball(self) -> None:
        config = GameConfig(
            obstacle_count=0,
            maximum_iterations=30,
            loose_ball_restart_iterations=3,
        )
        env = SoccerEnv(config)
        env.reset(12)
        env.possession = None
        env.ball_position = (90.0, 125.0)
        env.ball_velocity = (0.0, 0.0)
        env.ball_remaining_distance = 0.0

        events = []
        for _ in range(4):
            _, info = env.step({"move": "STAY"}, {"move": "STAY"})
            events.extend(info["events"])

        drop_ball = next(event for event in events if event["type"] == "drop_ball")
        self.assertEqual(drop_ball["reason"], "unclaimed_loose_ball")
        self.assertEqual(
            env.ball_position,
            (config.field_width / 2, config.field_height / 2),
        )
        self.assertEqual(env.loose_ball_steps, 0)

    def test_loose_ball_timer_resets_while_a_player_makes_progress(self) -> None:
        config = GameConfig(
            obstacle_count=0,
            maximum_iterations=30,
            loose_ball_restart_iterations=2,
        )
        env = SoccerEnv(config)
        env.reset(13)
        env.possession = None
        env.ball_position = (90.0, 70.0)
        env.ball_velocity = (0.0, 0.0)
        env.ball_remaining_distance = 0.0

        events = []
        for _ in range(5):
            _, info = env.step({"move": "UP_RIGHT"}, {"move": "DOWN_RIGHT"})
            events.extend(info["events"])

        self.assertFalse(any(event["type"] == "drop_ball" for event in events))

    def test_untrained_q_bot_uses_active_baseline_move(self) -> None:
        env = SoccerEnv(self.config)
        observation = env.reset(8)["player_2"]
        action = QLearningBot(seed=1).decide(observation)
        self.assertNotEqual(action["move"], "STAY")

    def test_demo_strategies_return_legal_active_actions(self) -> None:
        env = SoccerEnv(self.config)
        observations = env.reset(9)
        for policy, player_id in (
            (aggressive_action, "player_1"),
            (counter_action, "player_2"),
        ):
            action = policy(observations[player_id])
            self.assertIn(action["move"], DIRECTIONS)
            self.assertNotEqual(action["move"], "STAY")
            if "kick" in action:
                self.assertIn(action["kick"]["direction"], DIRECTIONS)

    def test_reinforcement_policy_learns_full_actions(self) -> None:
        env = SoccerEnv(self.config)
        observations = env.reset(10)
        policy = ReinforcementPolicy(seed=3, evaluation_epsilon=0)
        current = observations["player_1"]
        before = env.state()
        action_index = policy.choose_index(current, epsilon=0.2)
        action = policy.action_from_index(current, action_index)
        observations, info = env.step(action, practice_action(observations["player_2"]))
        reward = reinforcement_reward("player_1", before, env.state(), info["events"], action)
        policy.update(current, action_index, reward, observations["player_1"], env.done)
        key = policy.state_key(current)
        self.assertEqual(len(policy.q_table[key]), ACTION_COUNT)
        self.assertEqual(policy.visits[key], 1)
        self.assertIn(action["move"], DIRECTIONS)

    def test_reinforcement_policy_controls_ball_before_forward_kick(self) -> None:
        env = SoccerEnv(self.config)
        observation = env.reset(11)["player_1"]
        policy = ReinforcementPolicy(seed=4, evaluation_epsilon=0)
        for index in policy.valid_indices(observation):
            action = policy.action_from_index(observation, index)
            self.assertNotIn("kick", action)
            self.assertTrue(action["move"].startswith("UP"))
        observation["state"]["ball"]["possession_steps"] = 3
        for index in policy.valid_indices(observation):
            action = policy.action_from_index(observation, index)
            if "kick" in action:
                self.assertTrue(action["kick"]["direction"].startswith("UP"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from organizer_rl_bot.policy import OrganizerRLOpponent
from reference_bot.policy import choose_action
from soccer_env import GameConfig, SoccerEnv
from soccer_env.engine import DIRECTIONS
from soccer_env.web_viewer import ViewerData, _handler_for


BASE_DIRECTORY = Path(__file__).resolve().parents[1]


class StandaloneParticipantKitTests(unittest.TestCase):
    def test_official_environment_runs_without_organizer_folder(self) -> None:
        config = GameConfig.from_json(BASE_DIRECTORY / "config" / "game.json")
        env = SoccerEnv(config)
        observations = env.reset(4242)
        for _ in range(20):
            observations, _ = env.step(
                choose_action(observations["player_1"]),
                choose_action(observations["player_2"]),
            )
        self.assertEqual(env.iteration, 20)

    def test_organizer_rl_model_matches_manifest(self) -> None:
        manifest = json.loads(
            (BASE_DIRECTORY / "config" / "environment_manifest.json").read_text(encoding="utf-8")
        )
        model = BASE_DIRECTORY / manifest["organizer_rl_model"]
        self.assertEqual(hashlib.sha256(model.read_bytes()).hexdigest(), manifest["organizer_rl_sha256"])
        self.assertGreater(len(OrganizerRLOpponent().policy.q_table), 1000)

    def test_reference_and_rl_actions_are_legal(self) -> None:
        env = SoccerEnv(GameConfig.from_json(BASE_DIRECTORY / "config" / "game.json"))
        observation = env.reset(73)["player_1"]
        for action in (choose_action(observation), OrganizerRLOpponent().choose_action(observation)):
            self.assertIn(action["move"], DIRECTIONS)
            if "kick" in action:
                self.assertIn(action["kick"]["direction"], DIRECTIONS)
                self.assertIn(action["kick"]["power"], observation["action_space"]["kick"]["power"])

    def test_web_viewer_assets_and_demo_config_exist(self) -> None:
        for relative in (
            "viewer/index.html",
            "viewer/style.css",
            "viewer/viewer.js",
            "config/demo_match.json",
        ):
            self.assertTrue((BASE_DIRECTORY / relative).is_file(), relative)

    def test_web_viewer_serves_ui_and_state_api(self) -> None:
        data = ViewerData("live", {"seed": 9, "players": {}})
        server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_for(data))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            with urllib.request.urlopen(base + "/", timeout=2) as response:
                self.assertIn(b"AI Soccer Arena Viewer", response.read())
            with urllib.request.urlopen(base + "/api/info", timeout=2) as response:
                value = json.loads(response.read())
            self.assertEqual(value["metadata"]["seed"], 9)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from soccer_env import GameConfig
from soccer_env.tournament_setup import build_event, discover_submissions, safe_slug
from soccer_env.dashboard_server import TournamentControl
from run_event import unique_fixture_seed
from soccer_env.double_elimination import (
    bracket_pairings,
    maximum_fixture_count,
    run_double_elimination_event,
)
from soccer_env.match_runner import Competitor


class TournamentSetupTests(unittest.TestCase):
    def test_discovers_each_submission_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for folder, name in (("alpha", "Alpha FC"), ("beta", "Beta Bots")):
                team = root / folder
                team.mkdir()
                (team / "submission.json").write_text(
                    json.dumps({"name": name, "command": ["python", "-m", "team.bot"]}),
                    encoding="utf-8",
                )
            competitors = discover_submissions(root)
            self.assertEqual([item["name"] for item in competitors], ["Alpha FC", "Beta Bots"])
            self.assertTrue(all(Path(item["working_directory"]).is_absolute() for item in competitors))

    def test_duplicate_names_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for folder, name in (("one", "Same Team"), ("two", "same team")):
                team = root / folder
                team.mkdir()
                (team / "submission.json").write_text(
                    json.dumps({"name": name, "command": ["python", "bot.py"]}), encoding="utf-8"
                )
            with self.assertRaisesRegex(ValueError, "Duplicate team name"):
                discover_submissions(root)

    def test_event_uses_fixed_inputs_and_pacing(self) -> None:
        settings = {"seeds": [1, 2], "presentation_delay_seconds": 0.08}
        competitors = [
            {"name": "A", "command": ["python", "a.py"]},
            {"name": "B", "command": ["python", "b.py"]},
        ]
        event = build_event(settings, competitors, Path("game.json"), Path("logs"))
        self.assertEqual(event["competitors"], competitors)
        self.assertEqual(event["presentation_delay_seconds"], 0.08)
        self.assertTrue(Path(event["game_config"]).is_absolute())

    def test_team_name_becomes_safe_folder_name(self) -> None:
        self.assertEqual(safe_slug("  Team Falcon!  "), "team-falcon")

    def test_tournament_controls_configure_and_pause(self) -> None:
        control = TournamentControl(rounds=4)
        control.apply({"action": "configure", "rounds": 2})
        self.assertEqual(control.state()["rounds"], 2)
        control.apply({"action": "start"})
        self.assertFalse(control.state()["paused"])
        control.apply({"action": "pause"})
        self.assertTrue(control.state()["paused"])
        control.apply({"action": "speed", "speed": 4})
        self.assertEqual(control.delay(0.08), 0.02)

    def test_round_changes_are_published_before_start(self) -> None:
        control = TournamentControl(rounds=4)
        published: list[int] = []
        initial_seen = threading.Event()
        changed_seen = threading.Event()

        def publish(rounds: int) -> None:
            published.append(rounds)
            (initial_seen if rounds == 4 else changed_seen).set()

        worker = threading.Thread(target=control.wait_for_start, args=(publish,))
        worker.start()
        self.assertTrue(initial_seen.wait(1))
        control.apply({"action": "configure", "rounds": 2})
        self.assertTrue(changed_seen.wait(1))
        control.apply({"action": "start"})
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(published[-1], 2)

    def test_every_fixture_seed_is_unique_for_any_team_count(self) -> None:
        for team_count in (2, 3, 4, 9, 20):
            pairing_count = team_count * (team_count - 1) // 2
            seeds = {
                unique_fixture_seed(101 + round_index * 101, round_index, pairing_index, leg)
                for round_index in range(6)
                for pairing_index in range(pairing_count)
                for leg in range(2)
            }
            self.assertEqual(len(seeds), 6 * pairing_count * 2)

    def test_double_elimination_pairs_outer_seeds_and_preserves_a_bye(self) -> None:
        teams = [Competitor(name, ["bot"]) for name in ("A", "B", "C", "D", "E")]
        pairs, byes = bracket_pairings(teams)
        self.assertEqual([(a.name, b.name) for a, b in pairs], [("A", "E"), ("B", "D")])
        self.assertEqual([team.name for team in byes], ["C"])

    def test_double_elimination_match_limit_includes_reset_final(self) -> None:
        self.assertEqual(maximum_fixture_count(4, 1), 7)
        self.assertEqual(maximum_fixture_count(4, 3), 21)

    def test_four_team_double_elimination_reaches_a_champion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game_path = root / "game.json"
            game_path.write_text(json.dumps(GameConfig(obstacle_count=0).to_dict()), encoding="utf-8")
            event_path = root / "event.json"
            event_path.write_text(
                json.dumps(
                    {
                        "event_name": "Bracket Test",
                        "game_config": str(game_path),
                        "log_directory": str(root / "logs"),
                        "games_per_tie": 1,
                        "seeds": [101],
                        "competitors": [
                            {"name": name, "command": ["unused"]}
                            for name in ("A", "B", "C", "D")
                        ],
                    }
                ),
                encoding="utf-8",
            )
            counter = 0

            async def fake_match(_config, seed, player_1, player_2, *_args, **_kwargs):
                nonlocal counter
                counter += 1
                return {
                    "score": {"player_1": 1, "player_2": 0},
                    "iterations": 10,
                    "seed": seed,
                    "competitors": {"player_1": player_1.name, "player_2": player_2.name},
                }

            with patch("soccer_env.double_elimination.play_match", new=AsyncMock(side_effect=fake_match)):
                result = asyncio.run(run_double_elimination_event(event_path))

            self.assertEqual(result["champion"], "A")
            self.assertEqual(len(result["series"]), 6)
            self.assertEqual(len(result["results"]), 6)
            self.assertTrue(all(row["bracket_status"] in {"Champion", "Eliminated"} for row in result["standings"]))


if __name__ == "__main__":
    unittest.main()

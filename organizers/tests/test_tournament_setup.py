from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from soccer_env.tournament_setup import build_event, discover_submissions, safe_slug


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


if __name__ == "__main__":
    unittest.main()

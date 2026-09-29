from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from soccer_env.submission_checker import check_archive


POLICY = Path(__file__).resolve().parents[1] / "config" / "submission_policy.json"


class SubmissionCheckerTests(unittest.TestCase):
    def make_zip(self, files: dict[str, str]) -> Path:
        temporary = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        temporary.close()
        path = Path(temporary.name)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def valid_files(self) -> dict[str, str]:
        return {
            "submission.json": json.dumps(
                {
                    "name": "Test Team",
                    "command": ["python", "-m", "team.bot", "--model", "team/models/policy.json"],
                }
            ),
            "README.md": "# Test Team\n",
            "requirements.txt": "# standard library only\n",
            "team/__init__.py": "",
            "team/bot.py": "print('test')\n",
            "team/models/policy.json": "{}",
        }

    def test_valid_archive_passes(self) -> None:
        report = check_archive(self.make_zip(self.valid_files()), POLICY)
        self.assertTrue(report.passed, report.errors)
        self.assertEqual(report.team_name, "Test Team")
        self.assertIn("team/models/policy.json", report.model_files)

    def test_path_traversal_is_rejected(self) -> None:
        files = self.valid_files()
        files["../escape.py"] = ""
        report = check_archive(self.make_zip(files), POLICY)
        self.assertFalse(report.passed)
        self.assertTrue(any("Unsafe archive path" in error for error in report.errors))

    def test_unapproved_dependency_is_rejected(self) -> None:
        files = self.valid_files()
        files["requirements.txt"] = "requests==2.0\n"
        report = check_archive(self.make_zip(files), POLICY)
        self.assertFalse(report.passed)
        self.assertTrue(any("allowlist" in error for error in report.errors))

    def test_missing_launch_module_is_rejected(self) -> None:
        files = self.valid_files()
        files.pop("team/bot.py")
        report = check_archive(self.make_zip(files), POLICY)
        self.assertFalse(report.passed)
        self.assertTrue(any("Launch module" in error for error in report.errors))


if __name__ == "__main__":
    unittest.main()

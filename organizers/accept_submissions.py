from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
import zipfile
from argparse import Namespace
from pathlib import Path

from soccer_env.submission_checker import check_archive
from soccer_env.tournament_setup import safe_slug
from validate_submission import validate


BASE_DIRECTORY = Path(__file__).resolve().parent


async def accept_archive(archive_path: Path, skip_runtime_check: bool = False) -> bool:
    report_directory = BASE_DIRECTORY / "reports"
    accepted_directory = BASE_DIRECTORY / "submissions"
    archive_directory = BASE_DIRECTORY / "submission_archives"
    temporary_root = BASE_DIRECTORY / "tmp"
    report_directory.mkdir(parents=True, exist_ok=True)
    accepted_directory.mkdir(parents=True, exist_ok=True)
    archive_directory.mkdir(parents=True, exist_ok=True)
    temporary_root.mkdir(parents=True, exist_ok=True)

    report = check_archive(archive_path)
    report_path = report_directory / f"{archive_path.stem}.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    if not report.passed:
        print(f"REJECTED: {archive_path.name}")
        for error in report.errors:
            print(f"  - {error}")
        print(f"  Report: {report_path}")
        return False

    team_slug = safe_slug(report.team_name or archive_path.stem)
    destination = accepted_directory / team_slug
    archive_destination = archive_directory / f"{team_slug}.zip"
    if destination.exists():
        print(f"SKIPPED: {archive_path.name} - {destination} already exists")
        print("  Remove or rename the existing accepted folder only if this is an intentional replacement.")
        return False
    if archive_destination.exists():
        print(f"SKIPPED: the original archive already exists at {archive_destination}")
        return False

    with tempfile.TemporaryDirectory(prefix=f"{team_slug}-", dir=temporary_root) as temporary:
        staging = Path(temporary)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(staging)

        if not skip_runtime_check:
            print(f"Checking bot protocol: {report.team_name}")
            result = await validate(
                Namespace(
                    submission=str(staging / "submission.json"),
                    working_directory=str(staging),
                    game_config=str(BASE_DIRECTORY / "config" / "game.json"),
                    matches_per_side=1,
                    seed=7000,
                    timeout=2.0,
                    log_directory=str(BASE_DIRECTORY / "logs" / "validation" / team_slug),
                    python=sys.executable,
                )
            )
            if result:
                print(f"REJECTED: {archive_path.name} failed the live protocol check")
                return False

        shutil.copytree(staging, destination)
    shutil.move(str(archive_path), archive_destination)

    print(f"ACCEPTED: {report.team_name}")
    print(f"  Installed at: {destination}")
    print(f"  Original ZIP archived at: {archive_destination}")
    print(f"  SHA-256: {report.sha256}")
    print(f"  Report: {report_path}")
    return True


async def run(args: argparse.Namespace) -> int:
    incoming = Path(args.incoming).resolve()
    incoming.mkdir(parents=True, exist_ok=True)
    archives = sorted(incoming.glob("*.zip"), key=lambda path: path.name.casefold())
    if not archives:
        print(f"No ZIP files found in {incoming}")
        print("Copy participant ZIP files into that folder, then run this command again.")
        return 1

    accepted = 0
    for archive in archives:
        print(f"\n=== {archive.name} ===")
        accepted += int(await accept_archive(archive, args.skip_runtime_check))
    print(f"\nFinished: {accepted} accepted, {len(archives) - accepted} rejected or skipped.")
    print(f"Accepted teams: {BASE_DIRECTORY / 'submissions'}")
    return 0 if accepted == len(archives) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Check and install every participant ZIP from the organizer inbox")
    parser.add_argument("--incoming", default=str(BASE_DIRECTORY / "incoming"))
    parser.add_argument("--skip-runtime-check", action="store_true", help="Perform static checks only")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()

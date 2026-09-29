from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "team"


def discover_submissions(directory: str | Path) -> list[dict[str, Any]]:
    directory = Path(directory).resolve()
    competitors: list[dict[str, Any]] = []
    names: set[str] = set()
    if not directory.exists():
        return competitors

    for folder in sorted((item for item in directory.iterdir() if item.is_dir()), key=lambda item: item.name.casefold()):
        descriptor_path = folder / "submission.json"
        if not descriptor_path.is_file():
            continue
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        name = descriptor.get("name")
        command = descriptor.get("command")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{descriptor_path} has no valid team name")
        if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
            raise ValueError(f"{descriptor_path} has no valid command")
        folded = name.strip().casefold()
        if folded in names:
            raise ValueError(f"Duplicate team name: {name}")
        names.add(folded)
        competitors.append(
            {
                "name": name.strip(),
                "command": command,
                "working_directory": str(folder),
            }
        )
    return competitors


def build_event(settings: dict[str, Any], competitors: list[dict[str, Any]], game_config: Path, log_directory: Path) -> dict[str, Any]:
    if len(competitors) < 2:
        raise ValueError("At least two accepted team submissions are required")
    event = dict(settings)
    event["game_config"] = str(game_config.resolve())
    event["log_directory"] = str(log_directory.resolve())
    event["competitors"] = competitors
    return event

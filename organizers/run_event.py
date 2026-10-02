from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any, Callable

from soccer_env.double_elimination import run_double_elimination_event


BASE_DIRECTORY = Path(__file__).resolve().parent


def _cantor_pair(first: int, second: int) -> int:
    total = first + second
    return total * (total + 1) // 2 + second


def unique_fixture_seed(base_seed: int, round_index: int, pairing_index: int, leg: int) -> int:
    """Injectively encode fixture coordinates into a reproducible nonnegative seed."""
    seed_code = 2 * base_seed if base_seed >= 0 else -2 * base_seed - 1
    round_code = _cantor_pair(seed_code, round_index)
    fixture_code = _cantor_pair(pairing_index, leg)
    return _cantor_pair(round_code, fixture_code)


async def run_event(
    config_path: Path,
    status_callback: Callable[[dict[str, Any]], None] | None = None,
    control: Any | None = None,
) -> dict[str, Any]:
    """Run the standard double-elimination event."""
    return await run_double_elimination_event(config_path, status_callback, control)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a seeded double-elimination AI Soccer event")
    parser.add_argument(
        "--config",
        default=str(BASE_DIRECTORY / "config" / "event.json"),
        help="Event JSON file",
    )
    args = parser.parse_args()
    asyncio.run(run_event(Path(args.config)))


if __name__ == "__main__":
    main()

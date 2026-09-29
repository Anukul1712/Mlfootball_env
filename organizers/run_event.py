from __future__ import annotations

import argparse
import asyncio
import csv
import copy
import json
from itertools import combinations
from pathlib import Path
from typing import Any, Callable

from soccer_env import GameConfig
from soccer_env.match_runner import Competitor, load_competitor, play_match

BASE_DIRECTORY = Path(__file__).resolve().parent


def _standings_rows(table: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    rows = []
    for name, values in table.items():
        rows.append({"name": name, **values, "goal_difference": values["gf"] - values["ga"]})
    rows.sort(key=lambda row: row["name"].casefold())
    rows.sort(key=lambda row: (row["points"], row["goal_difference"], row["gf"]), reverse=True)
    return rows


async def run_event(
    config_path: Path,
    status_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    config_path = config_path.resolve()
    event = json.loads(config_path.read_text(encoding="utf-8"))
    game_config_path = Path(event["game_config"])
    if not game_config_path.is_absolute():
        game_config_path = config_path.parent / game_config_path
    game_config = GameConfig.from_json(game_config_path)
    competitors = [load_competitor(item, BASE_DIRECTORY) for item in event["competitors"]]
    seeds = [int(seed) for seed in event.get("seeds", [1])]
    swap_sides = bool(event.get("swap_sides", True))
    log_directory = Path(event.get("log_directory", "logs"))
    if not log_directory.is_absolute():
        log_directory = BASE_DIRECTORY / log_directory
    log_directory.mkdir(parents=True, exist_ok=True)
    table = {
        competitor.name: {"played": 0, "wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0, "points": 0}
        for competitor in competitors
    }

    fixtures: list[tuple[Competitor, Competitor, int]] = []
    for first, second in combinations(competitors, 2):
        for seed in seeds:
            fixtures.append((first, second, seed))
            if swap_sides:
                fixtures.append((second, first, seed))

    event_name = event.get("event_name", "AI Soccer Event")
    presentation_delay = max(0.0, float(event.get("presentation_delay_seconds", 0.0)))
    event_countdown = max(0, int(event.get("event_countdown_seconds", 0)))
    match_countdown = max(0, int(event.get("match_countdown_seconds", 0)))
    goal_pause = max(0.0, float(event.get("goal_pause_seconds", 0.0)))
    between_matches = max(0.0, float(event.get("between_matches_seconds", 0.0)))
    fixture_records = [
        {
            "number": number,
            "player_1": player_1.name,
            "player_2": player_2.name,
            "seed": seed,
            "status": "scheduled",
            "score": None,
            "iteration": 0,
            "result": None,
        }
        for number, (player_1, player_2, seed) in enumerate(fixtures, start=1)
    ]
    dashboard = {
        "event_name": event_name,
        "status": "running",
        "completed_matches": 0,
        "total_matches": len(fixtures),
        "active_match": None,
        "active_state": None,
        "phase": "welcome",
        "announcement": "The arena is getting ready",
        "countdown": None,
        "last_events": [],
        "fixtures": fixture_records,
        "standings": _standings_rows(table),
        "error": None,
    }

    def publish() -> None:
        if status_callback:
            status_callback(copy.deepcopy(dashboard))

    print(f"Event: {event_name} | matches={len(fixtures)}")
    publish()
    for remaining in range(event_countdown, 0, -1):
        dashboard["phase"] = "event_countdown"
        dashboard["countdown"] = remaining
        dashboard["announcement"] = f"Tournament begins in {remaining}"
        publish()
        await asyncio.sleep(1)
    dashboard["countdown"] = None
    results = []
    for number, (player_1, player_2, seed) in enumerate(fixtures, start=1):
        fixture_record = fixture_records[number - 1]
        fixture_record["status"] = "starting"
        dashboard["active_match"] = fixture_record
        print(f"\nMatch {number}/{len(fixtures)}: {player_1.name} vs {player_2.name} (seed {seed})")
        for remaining in range(match_countdown, 0, -1):
            dashboard["phase"] = "match_countdown"
            dashboard["countdown"] = remaining
            dashboard["announcement"] = f"{player_1.name} vs {player_2.name}"
            publish()
            await asyncio.sleep(1)
        dashboard["countdown"] = None
        dashboard["phase"] = "playing"
        dashboard["announcement"] = "KICK OFF!"
        fixture_record["status"] = "running"
        publish()

        def on_frame(state: dict[str, Any], info: dict[str, Any]) -> None:
            fixture_record["score"] = state["score"]
            fixture_record["iteration"] = state["iteration"]
            dashboard["active_state"] = state
            dashboard["last_events"] = info.get("events", [])
            goals = [event for event in info.get("events", []) if event.get("type") == "goal"]
            if goals:
                scorer = player_1.name if goals[-1]["scorer"] == "player_1" else player_2.name
                dashboard["phase"] = "goal"
                dashboard["announcement"] = f"GOAL! {scorer}"
            elif dashboard["phase"] == "goal":
                dashboard["phase"] = "playing"
                dashboard["announcement"] = "PLAY RESUMES"
            if info.get("events") or state["iteration"] % 2 == 0 or state["done"]:
                publish()

        result = await play_match(
            game_config,
            seed,
            player_1,
            player_2,
            float(event.get("action_timeout_seconds", 2.0)),
            log_directory,
            bool(event.get("show_each_iteration", False)),
            frame_callback=on_frame,
            iteration_delay_seconds=presentation_delay,
            goal_pause_seconds=goal_pause,
        )
        results.append(result)
        p1_score = result["score"]["player_1"]
        p2_score = result["score"]["player_2"]
        first_row, second_row = table[player_1.name], table[player_2.name]
        first_row["played"] += 1
        second_row["played"] += 1
        first_row["gf"] += p1_score
        first_row["ga"] += p2_score
        second_row["gf"] += p2_score
        second_row["ga"] += p1_score
        if p1_score > p2_score:
            first_row["wins"] += 1
            second_row["losses"] += 1
            first_row["points"] += 3
        elif p2_score > p1_score:
            second_row["wins"] += 1
            first_row["losses"] += 1
            second_row["points"] += 3
        else:
            first_row["draws"] += 1
            second_row["draws"] += 1
            first_row["points"] += 1
            second_row["points"] += 1

        fixture_record["status"] = "completed"
        fixture_record["score"] = result["score"]
        fixture_record["iteration"] = result["iterations"]
        fixture_record["result"] = result
        dashboard["completed_matches"] = number
        dashboard["standings"] = _standings_rows(table)
        dashboard["phase"] = "match_result"
        if p1_score > p2_score:
            dashboard["announcement"] = f"{player_1.name} wins {p1_score}-{p2_score}"
        elif p2_score > p1_score:
            dashboard["announcement"] = f"{player_2.name} wins {p2_score}-{p1_score}"
        else:
            dashboard["announcement"] = f"Draw: {p1_score}-{p2_score}"
        publish()
        if number < len(fixtures) and between_matches:
            await asyncio.sleep(between_matches)
        dashboard["active_match"] = None
        dashboard["active_state"] = None
        dashboard["last_events"] = []

    rows = _standings_rows(table)

    standings_path = log_directory / "standings.csv"
    with standings_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    results_path = log_directory / "event_results.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\nFinal standings")
    for position, row in enumerate(rows, start=1):
        print(
            f"{position:2}. {row['name']:<20} P={row['played']} W={row['wins']} "
            f"D={row['draws']} L={row['losses']} GD={row['goal_difference']:+d} Pts={row['points']}"
        )
    print(f"\nStandings: {standings_path.resolve()}")
    print(f"Results:   {results_path.resolve()}")
    dashboard["status"] = "complete"
    dashboard["standings"] = rows
    dashboard["active_match"] = None
    dashboard["phase"] = "complete"
    dashboard["countdown"] = None
    dashboard["announcement"] = f"CHAMPIONS: {rows[0]['name']}" if rows else "TOURNAMENT COMPLETE"
    publish()
    return {
        "event_name": event_name,
        "standings": rows,
        "results": results,
        "standings_path": str(standings_path.resolve()),
        "results_path": str(results_path.resolve()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a seeded round-robin AI Soccer event")
    parser.add_argument("--config", default=str(BASE_DIRECTORY / "config" / "event.json"), help="Event JSON file")
    args = parser.parse_args()
    asyncio.run(run_event(Path(args.config)))


if __name__ == "__main__":
    main()

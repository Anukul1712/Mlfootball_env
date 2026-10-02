from __future__ import annotations

import asyncio
import copy
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from .config import GameConfig
from .match_runner import Competitor, load_competitor, play_match


def _cantor_pair(first: int, second: int) -> int:
    total = first + second
    return total * (total + 1) // 2 + second


def fixture_seed(base_seed: int, stage: int, series: int, leg: int) -> int:
    seed_code = 2 * base_seed if base_seed >= 0 else -2 * base_seed - 1
    return _cantor_pair(_cantor_pair(seed_code, stage), _cantor_pair(series, leg))


def bracket_pairings(teams: list[Competitor]) -> tuple[list[tuple[Competitor, Competitor]], list[Competitor]]:
    """Pair the outer seeds and return any middle seed as a bye."""
    pairs: list[tuple[Competitor, Competitor]] = []
    left, right = 0, len(teams) - 1
    while left < right:
        pairs.append((teams[left], teams[right]))
        left += 1
        right -= 1
    return pairs, ([teams[left]] if left == right else [])


def maximum_fixture_count(team_count: int, games_per_tie: int) -> int:
    return max(0, (2 * team_count - 1) * games_per_tie)


def _rows(table: dict[str, dict[str, Any]], champion: str | None = None) -> list[dict[str, Any]]:
    rows = [
        {"name": name, **values, "goal_difference": values["gf"] - values["ga"]}
        for name, values in table.items()
    ]
    rows.sort(key=lambda row: row["name"].casefold())
    rows.sort(
        key=lambda row: (
            row["name"] == champion,
            row["bracket_losses"] < 2,
            -row["bracket_losses"],
            row["wins"],
            row["goal_difference"],
            row["gf"],
        ),
        reverse=True,
    )
    return rows


def _penalty_winner(first: Competitor, second: Competitor, seed: int) -> tuple[Competitor, Competitor, dict[str, int]]:
    digest = hashlib.sha256(f"{seed}|{first.name}|{second.name}".encode("utf-8")).digest()
    if digest[0] & 1:
        return first, second, {first.name: 5, second.name: 4}
    return second, first, {first.name: 4, second.name: 5}


async def run_double_elimination_event(
    config_path: Path,
    status_callback: Callable[[dict[str, Any]], None] | None = None,
    control: Any | None = None,
) -> dict[str, Any]:
    base_directory = Path(__file__).resolve().parent.parent
    config_path = config_path.resolve()
    event = json.loads(config_path.read_text(encoding="utf-8"))
    game_path = Path(event["game_config"])
    if not game_path.is_absolute():
        game_path = config_path.parent / game_path
    game_config = GameConfig.from_json(game_path)
    competitors = [load_competitor(item, base_directory) for item in event["competitors"]]
    if len(competitors) < 2:
        raise ValueError("Double elimination requires at least two teams")
    configured_seeds = [int(seed) for seed in event.get("seeds", [1])] or [1]
    log_directory = Path(event.get("log_directory", "logs"))
    if not log_directory.is_absolute():
        log_directory = base_directory / log_directory
    log_directory.mkdir(parents=True, exist_ok=True)

    table: dict[str, dict[str, Any]] = {
        team.name: {
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "gf": 0,
            "ga": 0,
            "bracket_losses": 0,
            "bracket_status": "Winners Bracket",
        }
        for team in competitors
    }
    losses = {team.name: 0 for team in competitors}
    fixture_records: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    series_results: list[dict[str, Any]] = []
    games_per_tie = max(1, int(event.get("games_per_tie", 1)))
    event_name = event.get("event_name", "AI Soccer Double-Elimination Championship")
    presentation_delay = max(0.0, float(event.get("presentation_delay_seconds", 0.0)))
    event_countdown = max(0, int(event.get("event_countdown_seconds", 0)))
    match_countdown = max(0, int(event.get("match_countdown_seconds", 0)))
    goal_pause = max(0.0, float(event.get("goal_pause_seconds", 0.0)))
    between_matches = max(0.0, float(event.get("between_matches_seconds", 0.0)))

    dashboard: dict[str, Any] = {
        "event_name": event_name,
        "format": "double_elimination",
        "status": "ready" if control else "running",
        "completed_matches": 0,
        "total_matches": maximum_fixture_count(len(competitors), games_per_tie),
        "active_match": None,
        "active_state": None,
        "phase": "welcome",
        "announcement": "Choose games per tie, then start the double-elimination tournament",
        "countdown": None,
        "last_events": [],
        "fixtures": fixture_records,
        "standings": _rows(table),
        "error": None,
    }

    def publish() -> None:
        dashboard["standings"] = _rows(table)
        if status_callback:
            status_callback(copy.deepcopy(dashboard))

    def seed_for(stage: int, series_number: int, leg: int) -> int:
        base_seed = configured_seeds[leg % len(configured_seeds)]
        return fixture_seed(base_seed, stage, series_number, leg)

    def sync_bracket_statuses() -> None:
        for team in competitors:
            bracket_losses = losses[team.name]
            table[team.name]["bracket_losses"] = bracket_losses
            table[team.name]["bracket_status"] = (
                "Eliminated" if bracket_losses >= 2
                else "Elimination Bracket" if bracket_losses == 1
                else "Winners Bracket"
            )

    def initial_preview(selected_games: int) -> None:
        nonlocal games_per_tie
        games_per_tie = max(1, int(selected_games))
        fixture_records.clear()
        first_pairs, _ = bracket_pairings(competitors)
        number = 1
        for series_number, (first, second) in enumerate(first_pairs, start=1):
            for leg in range(games_per_tie):
                home, away = (first, second) if leg % 2 == 0 else (second, first)
                fixture_records.append(
                    {
                        "number": number,
                        "player_1": home.name,
                        "player_2": away.name,
                        "seed": seed_for(1, series_number, leg),
                        "round": "Winners R1",
                        "bracket": "Winners Bracket",
                        "series_game": leg + 1,
                        "series_games": games_per_tie,
                        "status": "scheduled",
                        "score": None,
                        "iteration": 0,
                        "result": None,
                    }
                )
                number += 1
        dashboard["total_matches"] = maximum_fixture_count(len(competitors), games_per_tie)
        dashboard["announcement"] = (
            f"Double elimination | {games_per_tie} game{'s' if games_per_tie != 1 else ''} per tie | "
            f"up to {dashboard['total_matches']} matches"
        )
        publish()

    initial_preview(games_per_tie)
    if control:
        control.wait_for_start(initial_preview)
        dashboard["status"] = "running"
        dashboard["announcement"] = "The double-elimination bracket is ready"
        publish()

    for remaining in range(event_countdown, 0, -1):
        dashboard["phase"] = "event_countdown"
        dashboard["countdown"] = remaining
        dashboard["announcement"] = f"Tournament begins in {remaining}"
        publish()
        await asyncio.sleep(1)
    dashboard["countdown"] = None

    series_counter = 0
    stage = 0

    async def play_series(first: Competitor, second: Competitor, label: str, bracket: str) -> tuple[Competitor, Competitor]:
        nonlocal series_counter
        series_counter += 1
        series_number = series_counter
        aggregate = {first.name: 0, second.name: 0}
        played_records: list[dict[str, Any]] = []

        for leg in range(games_per_tie):
            home, away = (first, second) if leg % 2 == 0 else (second, first)
            seed = seed_for(stage, series_number, leg)
            existing = next(
                (
                    item for item in fixture_records
                    if item["status"] == "scheduled"
                    and item["round"] == label
                    and item["player_1"] == home.name
                    and item["player_2"] == away.name
                    and item["series_game"] == leg + 1
                ),
                None,
            )
            record = existing or {
                "number": len(fixture_records) + 1,
                "player_1": home.name,
                "player_2": away.name,
                "seed": seed,
                "round": label,
                "bracket": bracket,
                "series_game": leg + 1,
                "series_games": games_per_tie,
                "status": "scheduled",
                "score": None,
                "iteration": 0,
                "result": None,
            }
            if existing is None:
                fixture_records.append(record)
            record["seed"] = seed
            record["status"] = "starting"
            dashboard["active_match"] = record
            dashboard["phase"] = "fixture_preview"
            dashboard["announcement"] = f"NEXT: {bracket.upper()}"
            publish()
            print(f"\n{label} | Match {record['number']}: {home.name} vs {away.name} (seed {seed})")

            for remaining in range(match_countdown, 0, -1):
                dashboard["phase"] = "match_countdown"
                dashboard["countdown"] = remaining
                dashboard["announcement"] = f"{home.name} vs {away.name}"
                publish()
                await asyncio.sleep(1)
            dashboard["countdown"] = None
            dashboard["phase"] = "playing"
            dashboard["announcement"] = "KICK OFF!"
            record["status"] = "running"
            publish()

            def on_frame(state: dict[str, Any], info: dict[str, Any]) -> None:
                record["score"] = state["score"]
                record["iteration"] = state["iteration"]
                dashboard["active_state"] = state
                dashboard["last_events"] = info.get("events", [])
                goals = [event for event in info.get("events", []) if event.get("type") == "goal"]
                if goals:
                    scorer = home.name if goals[-1]["scorer"] == "player_1" else away.name
                    dashboard["phase"] = "goal"
                    dashboard["announcement"] = f"GOAL! {scorer}"
                elif dashboard["phase"] == "goal":
                    dashboard["phase"] = "playing"
                    dashboard["announcement"] = "PLAY RESUMES"
                if control or info.get("events") or state["iteration"] % 2 == 0 or state["done"]:
                    publish()

            result = await play_match(
                game_config,
                seed,
                home,
                away,
                float(event.get("action_timeout_seconds", 2.0)),
                log_directory,
                bool(event.get("show_each_iteration", False)),
                frame_callback=on_frame,
                iteration_delay_seconds=presentation_delay,
                goal_pause_seconds=goal_pause,
                iteration_gate=control.checkpoint if control else None,
                iteration_delay_provider=control.delay if control else None,
            )
            results.append(result)
            played_records.append(record)
            home_score = result["score"]["player_1"]
            away_score = result["score"]["player_2"]
            aggregate[home.name] += home_score
            aggregate[away.name] += away_score
            for team, goals_for, goals_against in ((home, home_score, away_score), (away, away_score, home_score)):
                row = table[team.name]
                row["played"] += 1
                row["gf"] += goals_for
                row["ga"] += goals_against
            if home_score > away_score:
                table[home.name]["wins"] += 1
                table[away.name]["losses"] += 1
            elif away_score > home_score:
                table[away.name]["wins"] += 1
                table[home.name]["losses"] += 1
            else:
                table[home.name]["draws"] += 1
                table[away.name]["draws"] += 1

            record["status"] = "completed"
            record["score"] = result["score"]
            record["iteration"] = result["iterations"]
            record["result"] = result
            dashboard["completed_matches"] += 1
            dashboard["phase"] = "match_result"
            dashboard["announcement"] = f"Full time: {home.name} {home_score}-{away_score} {away.name}"
            publish()
            if between_matches:
                await asyncio.sleep(between_matches)
            dashboard["active_state"] = None
            dashboard["last_events"] = []

        first_goals, second_goals = aggregate[first.name], aggregate[second.name]
        penalties = None
        if first_goals > second_goals:
            winner, loser = first, second
        elif second_goals > first_goals:
            winner, loser = second, first
        else:
            winner, loser, penalties = _penalty_winner(first, second, seed_for(stage, series_number, games_per_tie + 97))
            dashboard["announcement"] = (
                f"{winner.name} wins the tie on penalties "
                f"{max(penalties.values())}-{min(penalties.values())}"
            )
            played_records[-1]["tiebreak"] = {"type": "penalties", "score": penalties, "winner": winner.name}
            publish()

        series_results.append(
            {
                "round": label,
                "bracket": bracket,
                "teams": [first.name, second.name],
                "aggregate": {first.name: first_goals, second.name: second_goals},
                "winner": winner.name,
                "loser": loser.name,
                "penalties": penalties,
            }
        )
        return winner, loser

    champion: Competitor | None = None
    while champion is None:
        active = [team for team in competitors if losses[team.name] < 2]
        undefeated = [team for team in active if losses[team.name] == 0]
        elimination = [team for team in active if losses[team.name] == 1]

        if len(active) == 2 and len(undefeated) == 1 and len(elimination) == 1:
            stage += 1
            winner, loser = await play_series(undefeated[0], elimination[0], "Grand Final", "Grand Final")
            losses[loser.name] += 1
            sync_bracket_statuses()
            if losses[loser.name] >= 2:
                champion = winner
            else:
                stage += 1
                winner, loser = await play_series(undefeated[0], elimination[0], "Grand Final Reset", "Grand Final")
                losses[loser.name] += 1
                sync_bracket_statuses()
                champion = winner
            continue

        if len(active) == 2 and not undefeated:
            stage += 1
            winner, loser = await play_series(active[0], active[1], "Grand Final Reset", "Grand Final")
            losses[loser.name] += 1
            sync_bracket_statuses()
            champion = winner
            continue

        stage += 1
        winners_pairs, _ = bracket_pairings(undefeated)
        elimination_pairs, _ = bracket_pairings(elimination)
        for first, second in winners_pairs:
            _, loser = await play_series(first, second, f"Winners R{stage}", "Winners Bracket")
            losses[loser.name] += 1
            sync_bracket_statuses()
            publish()
        for first, second in elimination_pairs:
            _, loser = await play_series(first, second, f"Elimination R{stage}", "Elimination Bracket")
            losses[loser.name] += 1
            sync_bracket_statuses()
            publish()

    assert champion is not None
    for team in competitors:
        table[team.name]["bracket_losses"] = losses[team.name]
        table[team.name]["bracket_status"] = "Champion" if team.name == champion.name else (
            "Eliminated" if losses[team.name] >= 2 else "Runner-up"
        )
    rows = _rows(table, champion.name)
    dashboard["total_matches"] = dashboard["completed_matches"]

    standings_path = log_directory / "standings.csv"
    with standings_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    results_path = log_directory / "event_results.json"
    results_path.write_text(
        json.dumps({"format": "double_elimination", "champion": champion.name, "series": series_results, "matches": results}, indent=2),
        encoding="utf-8",
    )

    dashboard["status"] = "complete"
    dashboard["standings"] = rows
    dashboard["active_match"] = None
    dashboard["active_state"] = None
    dashboard["phase"] = "complete"
    dashboard["announcement"] = f"CHAMPIONS: {champion.name}"
    publish()
    print(f"\nChampions: {champion.name}")
    return {
        "event_name": event_name,
        "format": "double_elimination",
        "champion": champion.name,
        "standings": rows,
        "series": series_results,
        "results": results,
        "standings_path": str(standings_path.resolve()),
        "results_path": str(results_path.resolve()),
    }

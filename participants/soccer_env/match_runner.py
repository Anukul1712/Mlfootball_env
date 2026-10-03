from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import GameConfig
from .engine import SoccerEnv


@dataclass(frozen=True)
class Competitor:
    name: str
    command: list[str]
    working_directory: str | None = None


class AgentProcess:
    def __init__(self, competitor: Competitor, player_id: str, timeout_seconds: float):
        self.competitor = competitor
        self.player_id = player_id
        self.timeout_seconds = timeout_seconds
        self.process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        if not self.competitor.command:
            raise ValueError(f"No command configured for {self.competitor.name}")
        allowed_environment = {
            name: os.environ[name]
            for name in ("COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR")
            if name in os.environ
        }
        allowed_environment.update(
            PYTHONHASHSEED="0",
            PYTHONIOENCODING="utf-8",
            PYTHONNOUSERSITE="1",
            PYTHONUNBUFFERED="1",
        )
        self.process = await asyncio.create_subprocess_exec(
            *self.competitor.command,
            cwd=self.competitor.working_directory,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            limit=16_384,
            env=allowed_environment,
            # Bot diagnostics are allowed on stderr and should not be able to
            # fill an unread pipe and freeze a long match.
            stderr=None,
        )

    async def ask(self, message: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        assert self.process and self.process.stdin and self.process.stdout
        if self.process.returncode is not None:
            return {"move": "STAY"}, f"agent exited with code {self.process.returncode}"
        try:
            self.process.stdin.write((json.dumps(message, separators=(",", ":")) + "\n").encode())
            await self.process.stdin.drain()
            raw = await asyncio.wait_for(self.process.stdout.readline(), timeout=self.timeout_seconds)
            if not raw:
                return {"move": "STAY"}, "agent exited or closed stdout"
            if len(raw) > 8192:
                return {"move": "STAY"}, "action response exceeds 8192 bytes"
            response = json.loads(raw.decode("utf-8"))
            if not isinstance(response, dict):
                raise ValueError("response is not a JSON object")
            return response, None
        except asyncio.TimeoutError:
            return {"move": "STAY"}, f"action timeout after {self.timeout_seconds} seconds"
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            return {"move": "STAY"}, f"invalid response: {error}"
        except (BrokenPipeError, ConnectionResetError) as error:
            return {"move": "STAY"}, f"agent unavailable: {error}"

    async def finish(self, result: dict[str, Any]) -> None:
        if not self.process:
            return
        if self.process.stdin and not self.process.stdin.is_closing():
            try:
                self.process.stdin.write(
                    (json.dumps({"type": "match_end", "result": result}) + "\n").encode()
                )
                await self.process.stdin.drain()
                self.process.stdin.close()
            except (BrokenPipeError, ConnectionResetError):
                pass
        try:
            await asyncio.wait_for(self.process.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()


def _log_line(handle: Any, record: dict[str, Any]) -> None:
    handle.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
    handle.flush()


async def play_match(
    game_config: GameConfig,
    seed: int,
    player_1: Competitor,
    player_2: Competitor,
    timeout_seconds: float = 2.0,
    log_directory: str | Path = "logs",
    show_each_iteration: bool = False,
    state_callback: Callable[[dict[str, Any]], None] | None = None,
    frame_callback: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
    iteration_delay_seconds: float = 0.0,
    goal_pause_seconds: float = 0.0,
    iteration_gate: Callable[[], None] | None = None,
    iteration_delay_provider: Callable[[float], float] | None = None,
) -> dict[str, Any]:
    env = SoccerEnv(game_config)
    observations = env.reset(seed)
    match_id = uuid.uuid4().hex[:12]
    log_directory = Path(log_directory)
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / f"match_{match_id}_seed_{seed}.jsonl"

    agents = {
        "player_1": AgentProcess(player_1, "player_1", timeout_seconds),
        "player_2": AgentProcess(player_2, "player_2", timeout_seconds),
    }
    action_error_counts = {"player_1": 0, "player_2": 0}
    await asyncio.gather(*(agent.start() for agent in agents.values()))
    if state_callback:
        state_callback(env.state())

    with log_path.open("w", encoding="utf-8") as log:
        _log_line(
            log,
            {
                "type": "match_start",
                "match_id": match_id,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "seed": seed,
                "players": {"player_1": player_1.name, "player_2": player_2.name},
                "config": game_config.to_dict(),
                "initial_state": env.state(),
            },
        )

        try:
            while not env.done:
                if iteration_gate:
                    iteration_gate()
                state_before = env.state()
                requests = {
                    player_id: {
                        "type": "observation",
                        "match_id": match_id,
                        "observation": observations[player_id],
                    }
                    for player_id in ("player_1", "player_2")
                }
                answers = await asyncio.gather(
                    agents["player_1"].ask(requests["player_1"]),
                    agents["player_2"].ask(requests["player_2"]),
                )
                raw_actions = {"player_1": answers[0][0], "player_2": answers[1][0]}
                errors = {"player_1": answers[0][1], "player_2": answers[1][1]}
                for player_id, error in errors.items():
                    if error is not None:
                        action_error_counts[player_id] += 1
                observations, info = env.step(raw_actions["player_1"], raw_actions["player_2"])
                if state_callback:
                    state_callback(env.state())
                if frame_callback:
                    frame_callback(env.state(), info)
                _log_line(
                    log,
                    {
                        "type": "iteration",
                        "iteration": state_before["iteration"],
                        "state_before": state_before,
                        "raw_actions": raw_actions,
                        "action_errors": errors,
                        "actions_applied": info["actions_applied"],
                        "events": info["events"],
                        "state_after": env.state(),
                    },
                )
                if show_each_iteration:
                    ball = env.state()["ball"]
                    print(
                        f"iteration={env.iteration:03d} "
                        f"score={env.score['player_1']}-{env.score['player_2']} "
                        f"ball=({ball['x']:.1f},{ball['y']:.1f}) "
                        f"possession={ball['possession']}"
                    )
                for event in info["events"]:
                    if event["type"] == "goal":
                        print(
                            f"GOAL: {event['scorer']} | "
                            f"{player_1.name} {env.score['player_1']}-"
                            f"{env.score['player_2']} {player_2.name}"
                        )
                if goal_pause_seconds > 0 and any(event["type"] == "goal" for event in info["events"]):
                    await asyncio.sleep(goal_pause_seconds)
                delay = (
                    iteration_delay_provider(iteration_delay_seconds)
                    if iteration_delay_provider
                    else iteration_delay_seconds
                )
                if delay > 0:
                    await asyncio.sleep(delay)
        finally:
            result = env.result()
            result["match_id"] = match_id
            result["log_path"] = str(log_path.resolve())
            result["competitors"] = {"player_1": player_1.name, "player_2": player_2.name}
            result["action_error_counts"] = action_error_counts
            _log_line(log, {"type": "match_end", "result": result})
            await asyncio.gather(*(agent.finish(result) for agent in agents.values()))

    return result


def load_competitor(
    raw: dict[str, Any],
    default_working_directory: str | Path | None = None,
) -> Competitor:
    command = [str(part) for part in raw["command"]]
    if command and command[0].lower() in {"python", "python3"}:
        command[0] = sys.executable
    working_directory = raw.get("working_directory")
    if working_directory:
        working_path = Path(str(working_directory))
        if default_working_directory and not working_path.is_absolute():
            working_path = Path(default_working_directory) / working_path
        working_directory = str(working_path.resolve())
    elif default_working_directory:
        working_directory = str(Path(default_working_directory).resolve())
    return Competitor(
        name=str(raw["name"]),
        command=command,
        working_directory=str(working_directory) if working_directory else None,
    )

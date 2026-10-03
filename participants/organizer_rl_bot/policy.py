from __future__ import annotations

from pathlib import Path
from typing import Any


from soccer_env.reinforcement import ReinforcementPolicy


DEFAULT_MODEL = Path(__file__).resolve().parent / "models" / "balanced_united_rl.json"


class OrganizerRLOpponent:
    """Exact inference wrapper for the tournament's Balanced United RL model."""

    def __init__(self, model_path: str | Path = DEFAULT_MODEL) -> None:
        self.model_path = Path(model_path)
        self.policy = ReinforcementPolicy.load(self.model_path)

    def start_episode(self) -> None:
        # The organizer bot seeds its small evaluation exploration once per
        # match. Direct engine training reuses this object, so reset that match
        # marker before each episode just as a fresh tournament process would.
        self.policy._match_seeded = False

    def choose_action(self, observation: dict[str, Any]) -> dict[str, Any]:
        return self.policy.decide(observation)

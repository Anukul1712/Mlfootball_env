from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path


ROOT_DIRECTORY = Path(__file__).resolve().parents[1]
ORGANIZER_DIRECTORY = ROOT_DIRECTORY / "organizers"
sys.path.insert(0, str(ORGANIZER_DIRECTORY))

from soccer_env import GameConfig, SoccerEnv
from soccer_env.bots import aggressive_action, counter_action, practice_action
from soccer_env.reinforcement import ReinforcementPolicy, reinforcement_reward


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a full-action-space reinforcement-learning bot")
    parser.add_argument("--game-config", default=str(ORGANIZER_DIRECTORY / "config" / "game.json"))
    parser.add_argument("--episodes", type=int, default=2400)
    parser.add_argument("--output", default=str(Path(__file__).resolve().parent / "models" / "trained_rl.json"))
    parser.add_argument("--resume", help="Continue training an existing format-3 RL model")
    parser.add_argument("--seed", type=int, default=7301)
    args = parser.parse_args()

    source_config = GameConfig.from_json(args.game_config)
    training_values = source_config.to_dict()
    training_values["kick_distances"] = tuple(training_values["kick_distances"])
    training_values["maximum_iterations"] = min(240, source_config.maximum_iterations)
    training_values["maximum_goals"] = min(5, source_config.maximum_goals)
    config = GameConfig(**training_values)
    learner = (
        ReinforcementPolicy.load(args.resume)
        if args.resume
        else ReinforcementPolicy(seed=args.seed, evaluation_epsilon=0.05, safety_margin=0.6)
    )
    learner.model_seed = args.seed
    learner.evaluation_epsilon = 0.05
    learner.safety_margin = 0.6
    opponents = [practice_action, aggressive_action, counter_action]
    rng = random.Random(args.seed)
    totals = {"wins": 0, "draws": 0, "losses": 0}

    for episode in range(args.episodes):
        env = SoccerEnv(config)
        # Every episode uses a distinct deterministic layout. Alternating the
        # controlled side avoids learning only the opening-possession role.
        observations = env.reset(seed=args.seed + episode * 17)
        player_id = "player_1" if episode % 2 == 0 else "player_2"
        opponent_id = "player_2" if player_id == "player_1" else "player_1"
        opponent_policy = opponents[(episode // 2) % len(opponents)]
        epsilon = max(0.035, 0.72 * math.exp(-4.2 * episode / max(1, args.episodes)))

        while not env.done:
            current = observations[player_id]
            before = env.state()
            action_index = learner.choose_index(current, epsilon)
            learning_action = learner.action_from_index(current, action_index)
            opponent_action = opponent_policy(observations[opponent_id])
            if rng.random() < 0.025:
                opponent_action = {"move": rng.choice(observations[opponent_id]["action_space"]["move"][1:])}
            if player_id == "player_1":
                observations, info = env.step(learning_action, opponent_action)
            else:
                observations, info = env.step(opponent_action, learning_action)
            learner.update(
                current,
                action_index,
                reinforcement_reward(player_id, before, env.state(), info["events"], learning_action),
                observations[player_id],
                env.done,
            )

        winner = env.result()["winner"]
        totals["draws" if winner is None else "wins" if winner == player_id else "losses"] += 1
        interval = max(1, args.episodes // 12)
        if (episode + 1) % interval == 0:
            print(
                f"episode={episode + 1}/{args.episodes} states={len(learner.q_table)} "
                f"epsilon={epsilon:.3f} W/D/L={totals['wins']}/{totals['draws']}/{totals['losses']}"
            )

    learner.save(args.output)
    print(f"Saved {len(learner.q_table)} learned states to {Path(args.output).resolve()}")
    print(f"Training results: {totals}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT_DIRECTORY = Path(__file__).resolve().parents[1]
ORGANIZER_DIRECTORY = ROOT_DIRECTORY / "organizers"
sys.path.insert(0, str(ORGANIZER_DIRECTORY))

from soccer_env import GameConfig, SoccerEnv
from soccer_env.bots import QLearningBot, practice_action, shaped_reward


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the included Q-learning bot against the practice bot")
    parser.add_argument("--game-config", default=str(ORGANIZER_DIRECTORY / "config" / "game.json"))
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--output", default=str(Path(__file__).resolve().parent / "models" / "trained_bot.json"))
    parser.add_argument("--seed", type=int, default=1000)
    args = parser.parse_args()

    config = GameConfig.from_json(args.game_config)
    bot = QLearningBot(seed=args.seed)
    totals = {"wins": 0, "draws": 0, "losses": 0}

    for episode in range(args.episodes):
        env = SoccerEnv(config)
        observations = env.reset(seed=args.seed + episode)
        epsilon = max(0.05, 0.8 * math.exp(-3.0 * episode / max(1, args.episodes)))
        player_id = "player_1" if episode % 2 == 0 else "player_2"
        opponent_id = "player_2" if player_id == "player_1" else "player_1"

        while not env.done:
            current = observations[player_id]
            state_before = env.state()
            action_index = bot.choose_index(current, epsilon=epsilon)
            learning_action = bot.action_from_index(current, action_index)
            opponent_action = practice_action(observations[opponent_id])
            if player_id == "player_1":
                observations, info = env.step(learning_action, opponent_action)
            else:
                observations, info = env.step(opponent_action, learning_action)
            reward = shaped_reward(player_id, state_before, env.state(), info["events"])
            bot.update(
                current,
                action_index,
                reward,
                observations[player_id],
                env.done,
                learning_rate=0.18,
                discount=0.96,
            )

        result = env.result()
        if result["winner"] == player_id:
            totals["wins"] += 1
        elif result["winner"] is None:
            totals["draws"] += 1
        else:
            totals["losses"] += 1
        if (episode + 1) % max(1, args.episodes // 10) == 0:
            print(f"episode={episode + 1}/{args.episodes} states={len(bot.q_table)} epsilon={epsilon:.3f}")

    bot.save(args.output)
    print(f"Saved policy to {args.output}")
    print(f"Training results: {totals}")


if __name__ == "__main__":
    main()
